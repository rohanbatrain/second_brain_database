"""
Family Audit Manager for comprehensive SBD token audit trails and compliance reporting.

This module provides the FamilyAuditManager class, which handles:
- Comprehensive audit trail logging for all family SBD transactions
- Family member attribution in transaction notes
- Transaction history retrieval with family context
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

logger = get_logger(prefix="[FamilyAuditManager]")

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
    "family_member": "Family Member Transaction",
    "admin_action": "Administrative Action",
    "system_action": "System Automated Action",
    "recovery_action": "Account Recovery Action"
}


class FamilyAuditError(Exception):
    """Base family audit management exception."""
    
    def __init__(self, message: str, error_code: str = None, context: Dict[str, Any] = None):
        super().__init__(message)
        self.error_code = error_code or "FAMILY_AUDIT_ERROR"
        self.context = context or {}
        self.timestamp = datetime.now(timezone.utc)


class AuditTrailCorrupted(FamilyAuditError):
    """Audit trail integrity check failed."""
    
    def __init__(self, message: str, audit_id: str = None, expected_hash: str = None, actual_hash: str = None):
        super().__init__(message, "AUDIT_TRAIL_CORRUPTED", {
            "audit_id": audit_id,
            "expected_hash": expected_hash,
            "actual_hash": actual_hash
        })


class ComplianceReportError(FamilyAuditError):
    """Compliance report generation failed."""
    
    def __init__(self, message: str, report_type: str = None, family_id: str = None):
        super().__init__(message, "COMPLIANCE_REPORT_ERROR", {
            "report_type": report_type,
            "family_id": family_id
        })


class FamilyAuditManager:
    """
    Enterprise-grade family audit management system for SBD token compliance.
    
    This manager implements comprehensive audit trail management with:
    - Immutable audit trail logging with cryptographic integrity
    - Family member attribution in all transactions
    - Compliance reporting for regulatory requirements
    - Transaction history retrieval with family context
    - Audit trail export capabilities
    - Real-time audit event streaming
    """

    def __init__(self, db_manager=None) -> None:
        """
        Initialize FamilyAuditManager with dependency injection.
        
        Args:
            db_manager: Database manager for data operations
        """
        self.db_manager = db_manager or globals()['db_manager']
        self.logger = logger
        self.logger.debug("FamilyAuditManager initialized")

    async def log_sbd_transaction_audit(
        self, 
        family_id: str,
        transaction_id: str,
        transaction_type: str,
        amount: int,
        from_account: str,
        to_account: str,
        family_member_id: str,
        family_member_username: str,
        transaction_context: Dict[str, Any] = None,
        session: ClientSession = None
    ) -> Dict[str, Any]:
        """
        Log comprehensive audit trail for family SBD transactions.
        
        Args:
            family_id: ID of the family
            transaction_id: Unique transaction identifier
            transaction_type: Type of transaction (send, receive, spend, etc.)
            amount: Transaction amount
            from_account: Source account username
            to_account: Destination account username
            family_member_id: ID of family member performing transaction
            family_member_username: Username of family member
            transaction_context: Additional transaction context
            session: Database session for transaction safety
            
        Returns:
            Dict containing audit trail information
            
        Raises:
            FamilyAuditError: If audit logging fails
        """
        operation_context = {
            "family_id": family_id,
            "transaction_id": transaction_id,
            "operation": "log_sbd_transaction_audit",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        start_time = self.db_manager.log_query_start("family_audit_trails", "log_transaction", operation_context)
        
        try:
            now = datetime.now(timezone.utc)
            audit_id = f"audit_{uuid.uuid4().hex[:16]}"
            
            # Build comprehensive audit record
            audit_record = {
                "audit_id": audit_id,
                "family_id": family_id,
                "event_type": "sbd_transaction",
                "event_subtype": transaction_type,
                "timestamp": now,
                "transaction_details": {
                    "transaction_id": transaction_id,
                    "amount": amount,
                    "from_account": from_account,
                    "to_account": to_account,
                    "transaction_type": transaction_type
                },
                "family_member_attribution": {
                    "member_id": family_member_id,
                    "member_username": family_member_username,
                    "attribution_type": ATTRIBUTION_TYPES["family_member"],
                    "attribution_timestamp": now
                },
                "transaction_context": transaction_context or {},
                "compliance_metadata": {
                    "retention_until": now + timedelta(days=AUDIT_RETENTION_DAYS),
                    "regulatory_flags": [],
                    "export_eligible": True,
                    "data_classification": "financial_transaction"
                },
                "integrity": {
                    "created_at": now,
                    "created_by": "family_audit_manager",
                    "version": 1,
                    "hash": None  # Will be calculated below
                }
            }
            
            # Calculate integrity hash
            audit_record["integrity"]["hash"] = self._calculate_audit_hash(audit_record)
            
            # Store audit record
            audit_collection = self.db_manager.get_collection("family_audit_trails")
            await audit_collection.insert_one(audit_record, session=session)
            
            # Update family audit summary
            await self._update_family_audit_summary(family_id, audit_record, session)
            
            self.db_manager.log_query_success(
                "family_audit_trails", "log_transaction", start_time, 1,
                f"Audit trail logged: {audit_id}"
            )
            
            self.logger.info(
                "SBD transaction audit trail logged: %s for family %s by member %s",
                audit_id, family_id, family_member_username,
                extra={
                    "audit_id": audit_id,
                    "family_id": family_id,
                    "transaction_id": transaction_id,
                    "member_id": family_member_id,
                    "amount": amount,
                    "transaction_type": transaction_type
                }
            )
            
            return {
                "audit_id": audit_id,
                "family_id": family_id,
                "transaction_id": transaction_id,
                "timestamp": now,
                "integrity_hash": audit_record["integrity"]["hash"],
                "compliance_eligible": True
            }
            
        except Exception as e:
            self.db_manager.log_query_error("family_audit_trails", "log_transaction", start_time, e, operation_context)
            self.logger.error(
                "Failed to log SBD transaction audit for family %s: %s",
                family_id, e, exc_info=True,
                extra={
                    "family_id": family_id,
                    "transaction_id": transaction_id,
                    "member_id": family_member_id
                }
            )
            raise FamilyAuditError(f"Failed to log transaction audit: {str(e)}")

    async def enhance_transaction_with_family_attribution(
        self,
        transaction: Dict[str, Any],
        family_id: str,
        family_member_id: str,
        family_member_username: str,
        additional_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Enhance SBD transaction with comprehensive family member attribution.
        
        Args:
            transaction: Original transaction object
            family_id: ID of the family
            family_member_id: ID of family member performing transaction
            family_member_username: Username of family member
            additional_context: Additional context for attribution
            
        Returns:
            Enhanced transaction with family attribution
        """
        try:
            now = datetime.now(timezone.utc)
            
            # Create comprehensive family attribution
            family_attribution = {
                "family_id": family_id,
                "family_member_id": family_member_id,
                "family_member_username": family_member_username,
                "attribution_timestamp": now,
                "attribution_type": ATTRIBUTION_TYPES["family_member"]
            }
            
            # Add additional context if provided
            if additional_context:
                family_attribution["additional_context"] = additional_context
            
            # Enhance transaction note with family context
            original_note = transaction.get("note", "")
            family_note = f"Family transaction by @{family_member_username}"
            
            if original_note:
                enhanced_note = f"{original_note} ({family_note})"
            else:
                enhanced_note = family_note
            
            # Create enhanced transaction
            enhanced_transaction = transaction.copy()
            enhanced_transaction.update({
                "note": enhanced_note,
                "family_attribution": family_attribution,
                "compliance_metadata": {
                    "family_transaction": True,
                    "audit_eligible": True,
                    "attribution_complete": True,
                    "enhanced_at": now
                }
            })
            
            self.logger.debug(
                "Transaction enhanced with family attribution: %s for family %s",
                transaction.get("transaction_id", "unknown"), family_id,
                extra={
                    "family_id": family_id,
                    "member_id": family_member_id,
                    "transaction_id": transaction.get("transaction_id")
                }
            )
            
            return enhanced_transaction
            
        except Exception as e:
            self.logger.error(
                "Failed to enhance transaction with family attribution: %s", e,
                exc_info=True,
                extra={
                    "family_id": family_id,
                    "member_id": family_member_id,
                    "transaction_id": transaction.get("transaction_id")
                }
            )
            # Return original transaction if enhancement fails
            return transaction

    async def get_family_transaction_history_with_context(
        self,
        family_id: str,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_types: Optional[List[str]] = None,
        include_audit_trail: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Retrieve family transaction history with comprehensive context and audit trails.
        
        Args:
            family_id: ID of the family
            user_id: ID of user requesting history (for permission check)
            start_date: Start date for transaction history
            end_date: End date for transaction history
            transaction_types: Filter by transaction types
            include_audit_trail: Whether to include audit trail information
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip
            
        Returns:
            Dict containing transaction history with context
            
        Raises:
            FamilyAuditError: If retrieval fails
        """
        operation_context = {
            "family_id": family_id,
            "user_id": user_id,
            "operation": "get_transaction_history_with_context",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        start_time = self.db_manager.log_query_start("family_audit_trails", "get_history", operation_context)
        
        try:
            # Verify user has permission to access family transaction history
            await self._verify_family_access_permission(family_id, user_id)
            
            # Build query filters
            query_filters = {"family_id": family_id}
            
            if start_date or end_date:
                timestamp_filter = {}
                if start_date:
                    timestamp_filter["$gte"] = start_date
                if end_date:
                    timestamp_filter["$lte"] = end_date
                query_filters["timestamp"] = timestamp_filter
            
            if transaction_types:
                query_filters["event_subtype"] = {"$in": transaction_types}
            
            # Get audit trails
            audit_collection = self.db_manager.get_collection("family_audit_trails")
            
            # Get total count
            total_count = await audit_collection.count_documents(query_filters)
            
            # Get paginated results
            audit_cursor = audit_collection.find(query_filters).sort("timestamp", -1).skip(offset).limit(limit)
            audit_records = await audit_cursor.to_list(length=limit)
            
            # Get family SBD account transactions for correlation
            family_transactions = await self._get_family_sbd_transactions(family_id, start_date, end_date, limit)
            
            # Build comprehensive response
            response = {
                "family_id": family_id,
                "query_metadata": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                    "transaction_types": transaction_types,
                    "total_count": total_count,
                    "returned_count": len(audit_records),
                    "limit": limit,
                    "offset": offset,
                    "has_more": total_count > (offset + limit)
                },
                "transactions": [],
                "audit_summary": {
                    "total_audit_records": total_count,
                    "date_range": {
                        "earliest": None,
                        "latest": None
                    },
                    "transaction_types_found": set(),
                    "family_members_involved": set()
                }
            }
            
            # Process audit records and correlate with transactions
            for audit_record in audit_records:
                transaction_data = {
                    "audit_id": audit_record["audit_id"],
                    "timestamp": audit_record["timestamp"],
                    "transaction_details": audit_record["transaction_details"],
                    "family_member_attribution": audit_record["family_member_attribution"],
                    "transaction_context": audit_record.get("transaction_context", {}),
                    "compliance_metadata": audit_record.get("compliance_metadata", {})
                }
                
                # Add audit trail if requested
                if include_audit_trail:
                    transaction_data["audit_trail"] = {
                        "integrity_hash": audit_record["integrity"]["hash"],
                        "created_at": audit_record["integrity"]["created_at"],
                        "version": audit_record["integrity"]["version"]
                    }
                
                # Find corresponding SBD transaction
                transaction_id = audit_record["transaction_details"]["transaction_id"]
                sbd_transaction = next(
                    (t for t in family_transactions if t.get("transaction_id") == transaction_id),
                    None
                )
                
                if sbd_transaction:
                    transaction_data["sbd_transaction"] = sbd_transaction
                
                response["transactions"].append(transaction_data)
                
                # Update summary statistics
                response["audit_summary"]["transaction_types_found"].add(audit_record["event_subtype"])
                response["audit_summary"]["family_members_involved"].add(
                    audit_record["family_member_attribution"]["member_username"]
                )
                
                # Update date range
                timestamp = audit_record["timestamp"]
                if not response["audit_summary"]["date_range"]["earliest"] or timestamp < response["audit_summary"]["date_range"]["earliest"]:
                    response["audit_summary"]["date_range"]["earliest"] = timestamp
                if not response["audit_summary"]["date_range"]["latest"] or timestamp > response["audit_summary"]["date_range"]["latest"]:
                    response["audit_summary"]["date_range"]["latest"] = timestamp
            
            # Convert sets to lists for JSON serialization
            response["audit_summary"]["transaction_types_found"] = list(response["audit_summary"]["transaction_types_found"])
            response["audit_summary"]["family_members_involved"] = list(response["audit_summary"]["family_members_involved"])
            
            self.db_manager.log_query_success(
                "family_audit_trails", "get_history", start_time, len(audit_records),
                f"Transaction history retrieved for family {family_id}"
            )
            
            self.logger.info(
                "Family transaction history retrieved: %d records for family %s by user %s",
                len(audit_records), family_id, user_id,
                extra={
                    "family_id": family_id,
                    "user_id": user_id,
                    "record_count": len(audit_records),
                    "total_count": total_count
                }
            )
            
            return response
            
        except Exception as e:
            self.db_manager.log_query_error("family_audit_trails", "get_history", start_time, e, operation_context)
            self.logger.error(
                "Failed to retrieve family transaction history for family %s: %s",
                family_id, e, exc_info=True,
                extra={
                    "family_id": family_id,
                    "user_id": user_id
                }
            )
            raise FamilyAuditError(f"Failed to retrieve transaction history: {str(e)}")

    async def generate_compliance_report(
        self,
        family_id: str,
        user_id: str,
        report_type: str = "comprehensive",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        export_format: str = "json"
    ) -> Dict[str, Any]:
        """
        Generate comprehensive compliance report for family SBD transactions.
        
        Args:
            family_id: ID of the family
            user_id: ID of user requesting report (must be admin)
            report_type: Type of report (comprehensive, summary, transactions_only)
            start_date: Start date for report period
            end_date: End date for report period
            export_format: Format for export (json, csv, pdf)
            
        Returns:
            Dict containing compliance report
            
        Raises:
            ComplianceReportError: If report generation fails
        """
        operation_context = {
            "family_id": family_id,
            "user_id": user_id,
            "report_type": report_type,
            "operation": "generate_compliance_report",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        start_time = self.db_manager.log_query_start("family_audit_trails", "compliance_report", operation_context)
        
        try:
            # Verify user is family admin
            await self._verify_family_admin_permission(family_id, user_id)
            
            # Validate export format
            if export_format not in COMPLIANCE_REPORT_FORMATS:
                raise ComplianceReportError(
                    f"Invalid export format: {export_format}",
                    report_type=report_type,
                    family_id=family_id
                )
            
            now = datetime.now(timezone.utc)
            report_id = f"compliance_{uuid.uuid4().hex[:16]}"
            
            # Set default date range if not provided
            if not start_date:
                start_date = now - timedelta(days=365)  # Last year
            if not end_date:
                end_date = now
            
            # Get family information
            family = await self._get_family_by_id(family_id)
            
            # Get comprehensive transaction history
            transaction_history = await self.get_family_transaction_history_with_context(
                family_id, user_id, start_date, end_date, include_audit_trail=True, limit=10000
            )
            
            # Generate compliance statistics
            compliance_stats = await self._generate_compliance_statistics(
                family_id, start_date, end_date, transaction_history["transactions"]
            )
            
            # Build comprehensive compliance report
            compliance_report = {
                "report_metadata": {
                    "report_id": report_id,
                    "report_type": report_type,
                    "export_format": export_format,
                    "generated_at": now,
                    "generated_by": user_id,
                    "report_period": {
                        "start_date": start_date,
                        "end_date": end_date,
                        "duration_days": (end_date - start_date).days
                    }
                },
                "family_information": {
                    "family_id": family_id,
                    "family_name": family["name"],
                    "admin_count": len(family["admin_user_ids"]),
                    "member_count": family["member_count"],
                    "sbd_account_username": family["sbd_account"]["account_username"],
                    "account_status": "frozen" if family["sbd_account"]["is_frozen"] else "active"
                },
                "compliance_statistics": compliance_stats,
                "transaction_summary": {
                    "total_transactions": len(transaction_history["transactions"]),
                    "total_amount_transferred": sum(
                        t["transaction_details"]["amount"] for t in transaction_history["transactions"]
                    ),
                    "unique_family_members": len(transaction_history["audit_summary"]["family_members_involved"]),
                    "transaction_types": transaction_history["audit_summary"]["transaction_types_found"]
                },
                "audit_integrity": {
                    "total_audit_records": transaction_history["audit_summary"]["total_audit_records"],
                    "integrity_verified": True,  # Will be updated by integrity check
                    "missing_audit_trails": [],
                    "corrupted_records": []
                }
            }
            
            # Include detailed transactions if comprehensive report
            if report_type == "comprehensive":
                compliance_report["detailed_transactions"] = transaction_history["transactions"]
            
            # Perform audit trail integrity check
            integrity_results = await self._verify_audit_trail_integrity(family_id, start_date, end_date)
            compliance_report["audit_integrity"].update(integrity_results)
            
            # Log compliance report generation
            await self._log_compliance_report_generation(report_id, family_id, user_id, report_type)
            
            self.db_manager.log_query_success(
                "family_audit_trails", "compliance_report", start_time, 1,
                f"Compliance report generated: {report_id}"
            )
            
            self.logger.info(
                "Compliance report generated: %s for family %s by user %s",
                report_id, family_id, user_id,
                extra={
                    "report_id": report_id,
                    "family_id": family_id,
                    "user_id": user_id,
                    "report_type": report_type,
                    "transaction_count": len(transaction_history["transactions"])
                }
            )
            
            return compliance_report
            
        except Exception as e:
            self.db_manager.log_query_error("family_audit_trails", "compliance_report", start_time, e, operation_context)
            self.logger.error(
                "Failed to generate compliance report for family %s: %s",
                family_id, e, exc_info=True,
                extra={
                    "family_id": family_id,
                    "user_id": user_id,
                    "report_type": report_type
                }
            )
            raise ComplianceReportError(
                f"Failed to generate compliance report: {str(e)}",
                report_type=report_type,
                family_id=family_id
            )

    def _calculate_audit_hash(self, audit_record: Dict[str, Any]) -> str:
        """
        Calculate cryptographic hash for audit record integrity.
        
        Args:
            audit_record: Audit record to hash
            
        Returns:
            Hexadecimal hash string
        """
        try:
            # Create a copy without the hash field for calculation
            record_copy = audit_record.copy()
            if "integrity" in record_copy:
                record_copy["integrity"] = record_copy["integrity"].copy()
                record_copy["integrity"].pop("hash", None)
            
            # Convert to deterministic JSON string
            record_json = json.dumps(record_copy, sort_keys=True, default=str)
            
            # Calculate SHA-256 hash
            hash_object = hashlib.sha256(record_json.encode('utf-8'))
            return hash_object.hexdigest()
            
        except Exception as e:
            self.logger.error("Failed to calculate audit hash: %s", e, exc_info=True)
            return f"hash_error_{uuid.uuid4().hex[:8]}"

    async def _update_family_audit_summary(
        self,
        family_id: str,
        audit_record: Dict[str, Any],
        session: ClientSession = None
    ) -> None:
        """
        Update family audit summary with new audit record.
        
        Args:
            family_id: ID of the family
            audit_record: New audit record
            session: Database session for transaction safety
        """
        try:
            families_collection = self.db_manager.get_collection("families")
            
            update_query = {
                "$inc": {
                    "audit_summary.total_audit_records": 1,
                    f"audit_summary.event_counts.{audit_record['event_type']}": 1
                },
                "$set": {
                    "audit_summary.last_audit_at": audit_record["timestamp"],
                    "audit_summary.last_audit_id": audit_record["audit_id"]
                }
            }
            
            await families_collection.update_one(
                {"family_id": family_id},
                update_query,
                session=session
            )
            
        except Exception as e:
            self.logger.warning(
                "Failed to update family audit summary for %s: %s",
                family_id, e
            )

    async def _verify_family_access_permission(self, family_id: str, user_id: str) -> None:
        """
        Verify user has permission to access family audit information.
        
        Args:
            family_id: ID of the family
            user_id: ID of user requesting access
            
        Raises:
            FamilyAuditError: If user lacks permission
        """
        try:
            families_collection = self.db_manager.get_collection("families")
            family = await families_collection.find_one({"family_id": family_id})
            
            if not family:
                raise FamilyAuditError(f"Family not found: {family_id}")
            
            # Check if user is family member
            users_collection = self.db_manager.get_collection("users")
            user = await users_collection.find_one({"_id": user_id})
            
            if not user:
                raise FamilyAuditError(f"User not found: {user_id}")
            
            # Check family membership
            family_memberships = user.get("family_memberships", [])
            is_member = any(
                membership["family_id"] == family_id 
                for membership in family_memberships
            )
            
            if not is_member:
                raise FamilyAuditError(
                    "User does not have permission to access family audit information",
                    error_code="INSUFFICIENT_PERMISSIONS"
                )
                
        except FamilyAuditError:
            raise
        except Exception as e:
            raise FamilyAuditError(f"Failed to verify family access permission: {str(e)}")

    async def _verify_family_admin_permission(self, family_id: str, user_id: str) -> None:
        """
        Verify user has admin permission for family.
        
        Args:
            family_id: ID of the family
            user_id: ID of user requesting access
            
        Raises:
            FamilyAuditError: If user lacks admin permission
        """
        try:
            families_collection = self.db_manager.get_collection("families")
            family = await families_collection.find_one({"family_id": family_id})
            
            if not family:
                raise FamilyAuditError(f"Family not found: {family_id}")
            
            if user_id not in family["admin_user_ids"]:
                raise FamilyAuditError(
                    "User does not have admin permission for family",
                    error_code="INSUFFICIENT_ADMIN_PERMISSIONS"
                )
                
        except FamilyAuditError:
            raise
        except Exception as e:
            raise FamilyAuditError(f"Failed to verify family admin permission: {str(e)}")

    async def _get_family_by_id(self, family_id: str) -> Dict[str, Any]:
        """
        Get family by ID.
        
        Args:
            family_id: ID of the family
            
        Returns:
            Family document
            
        Raises:
            FamilyAuditError: If family not found
        """
        try:
            families_collection = self.db_manager.get_collection("families")
            family = await families_collection.find_one({"family_id": family_id})
            
            if not family:
                raise FamilyAuditError(f"Family not found: {family_id}")
            
            return family
            
        except FamilyAuditError:
            raise
        except Exception as e:
            raise FamilyAuditError(f"Failed to get family: {str(e)}")

    async def _get_family_sbd_transactions(
        self,
        family_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get family SBD account transactions.
        
        Args:
            family_id: ID of the family
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum transactions to return
            
        Returns:
            List of SBD transactions
        """
        try:
            # Get family to find SBD account username
            family = await self._get_family_by_id(family_id)
            sbd_username = family["sbd_account"]["account_username"]
            
            # Get SBD account transactions
            users_collection = self.db_manager.get_collection("users")
            user_doc = await users_collection.find_one(
                {"username": sbd_username, "is_virtual_account": True}
            )
            
            if not user_doc:
                return []
            
            transactions = user_doc.get("sbd_tokens_transactions", [])
            
            # Filter by date range if provided
            if start_date or end_date:
                filtered_transactions = []
                for txn in transactions:
                    txn_timestamp = datetime.fromisoformat(txn["timestamp"].replace('Z', '+00:00'))
                    
                    if start_date and txn_timestamp < start_date:
                        continue
                    if end_date and txn_timestamp > end_date:
                        continue
                    
                    filtered_transactions.append(txn)
                
                transactions = filtered_transactions
            
            # Sort by timestamp (newest first) and limit
            transactions.sort(key=lambda x: x["timestamp"], reverse=True)
            return transactions[:limit]
            
        except Exception as e:
            self.logger.warning(
                "Failed to get family SBD transactions for %s: %s",
                family_id, e
            )
            return []

    async def _generate_compliance_statistics(
        self,
        family_id: str,
        start_date: datetime,
        end_date: datetime,
        transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate compliance statistics for the report period.
        
        Args:
            family_id: ID of the family
            start_date: Start date of report period
            end_date: End date of report period
            transactions: List of transactions to analyze
            
        Returns:
            Dict containing compliance statistics
        """
        try:
            stats = {
                "transaction_volume": {
                    "total_transactions": len(transactions),
                    "total_amount": sum(t["transaction_details"]["amount"] for t in transactions),
                    "average_transaction_amount": 0,
                    "largest_transaction": 0,
                    "smallest_transaction": float('inf') if transactions else 0
                },
                "member_activity": {},
                "transaction_patterns": {
                    "by_type": {},
                    "by_day_of_week": {},
                    "by_hour_of_day": {}
                },
                "compliance_flags": [],
                "risk_indicators": []
            }
            
            if not transactions:
                return stats
            
            # Calculate transaction volume statistics
            amounts = [t["transaction_details"]["amount"] for t in transactions]
            stats["transaction_volume"]["average_transaction_amount"] = sum(amounts) / len(amounts)
            stats["transaction_volume"]["largest_transaction"] = max(amounts)
            stats["transaction_volume"]["smallest_transaction"] = min(amounts)
            
            # Analyze member activity
            for txn in transactions:
                member_username = txn["family_member_attribution"]["member_username"]
                if member_username not in stats["member_activity"]:
                    stats["member_activity"][member_username] = {
                        "transaction_count": 0,
                        "total_amount": 0,
                        "transaction_types": set()
                    }
                
                stats["member_activity"][member_username]["transaction_count"] += 1
                stats["member_activity"][member_username]["total_amount"] += txn["transaction_details"]["amount"]
                stats["member_activity"][member_username]["transaction_types"].add(
                    txn["transaction_details"]["transaction_type"]
                )
            
            # Convert sets to lists for JSON serialization
            for member_data in stats["member_activity"].values():
                member_data["transaction_types"] = list(member_data["transaction_types"])
            
            # Analyze transaction patterns
            for txn in transactions:
                txn_type = txn["transaction_details"]["transaction_type"]
                stats["transaction_patterns"]["by_type"][txn_type] = stats["transaction_patterns"]["by_type"].get(txn_type, 0) + 1
                
                # Analyze temporal patterns
                timestamp = txn["timestamp"]
                day_of_week = timestamp.strftime("%A")
                hour_of_day = timestamp.hour
                
                stats["transaction_patterns"]["by_day_of_week"][day_of_week] = stats["transaction_patterns"]["by_day_of_week"].get(day_of_week, 0) + 1
                stats["transaction_patterns"]["by_hour_of_day"][str(hour_of_day)] = stats["transaction_patterns"]["by_hour_of_day"].get(str(hour_of_day), 0) + 1
            
            # Check for compliance flags and risk indicators
            if stats["transaction_volume"]["largest_transaction"] > 10000:  # Large transaction threshold
                stats["compliance_flags"].append("Large transaction detected")
            
            if len(set(t["family_member_attribution"]["member_username"] for t in transactions)) == 1:
                stats["risk_indicators"].append("All transactions by single member")
            
            return stats
            
        except Exception as e:
            self.logger.warning(
                "Failed to generate compliance statistics for %s: %s",
                family_id, e
            )
            return {"error": f"Failed to generate statistics: {str(e)}"}

    async def _verify_audit_trail_integrity(
        self,
        family_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Verify integrity of audit trail records.
        
        Args:
            family_id: ID of the family
            start_date: Start date for verification
            end_date: End date for verification
            
        Returns:
            Dict containing integrity verification results
        """
        try:
            audit_collection = self.db_manager.get_collection("family_audit_trails")
            
            query = {
                "family_id": family_id,
                "timestamp": {"$gte": start_date, "$lte": end_date}
            }
            
            audit_records = await audit_collection.find(query).to_list(length=None)
            
            integrity_results = {
                "total_records_checked": len(audit_records),
                "integrity_verified": True,
                "corrupted_records": [],
                "missing_hashes": [],
                "verification_timestamp": datetime.now(timezone.utc)
            }
            
            for record in audit_records:
                # Check if hash exists
                if not record.get("integrity", {}).get("hash"):
                    integrity_results["missing_hashes"].append(record["audit_id"])
                    integrity_results["integrity_verified"] = False
                    continue
                
                # Verify hash integrity
                expected_hash = self._calculate_audit_hash(record)
                actual_hash = record["integrity"]["hash"]
                
                if expected_hash != actual_hash:
                    integrity_results["corrupted_records"].append({
                        "audit_id": record["audit_id"],
                        "expected_hash": expected_hash,
                        "actual_hash": actual_hash
                    })
                    integrity_results["integrity_verified"] = False
            
            return integrity_results
            
        except Exception as e:
            self.logger.warning(
                "Failed to verify audit trail integrity for %s: %s",
                family_id, e
            )
            return {
                "total_records_checked": 0,
                "integrity_verified": False,
                "error": f"Verification failed: {str(e)}",
                "verification_timestamp": datetime.now(timezone.utc)
            }

    async def _log_compliance_report_generation(
        self,
        report_id: str,
        family_id: str,
        user_id: str,
        report_type: str
    ) -> None:
        """
        Log compliance report generation for audit purposes.
        
        Args:
            report_id: ID of the generated report
            family_id: ID of the family
            user_id: ID of user who generated report
            report_type: Type of report generated
        """
        try:
            audit_record = {
                "audit_id": f"audit_{uuid.uuid4().hex[:16]}",
                "family_id": family_id,
                "event_type": "compliance_export",
                "event_subtype": "report_generation",
                "timestamp": datetime.now(timezone.utc),
                "compliance_export_details": {
                    "report_id": report_id,
                    "report_type": report_type,
                    "generated_by": user_id
                },
                "family_member_attribution": {
                    "member_id": user_id,
                    "attribution_type": ATTRIBUTION_TYPES["admin_action"]
                },
                "compliance_metadata": {
                    "retention_until": datetime.now(timezone.utc) + timedelta(days=AUDIT_RETENTION_DAYS),
                    "regulatory_flags": ["compliance_report"],
                    "export_eligible": True,
                    "data_classification": "compliance_report"
                }
            }
            
            audit_record["integrity"] = {
                "created_at": audit_record["timestamp"],
                "created_by": "family_audit_manager",
                "version": 1,
                "hash": self._calculate_audit_hash(audit_record)
            }
            
            audit_collection = self.db_manager.get_collection("family_audit_trails")
            await audit_collection.insert_one(audit_record)
            
        except Exception as e:
            self.logger.warning(
                "Failed to log compliance report generation: %s", e
            )


# Global instance for dependency injection
family_audit_manager = FamilyAuditManager()