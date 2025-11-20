"""
Team Wallet Manager for handling team SBD token management.

This module provides the TeamWalletManager class, which manages team SBD accounts,
token requests, transfers, permissions, and audit logging following the established
patterns from the family wallet system.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from pymongo.client_session import ClientSession
from pymongo.errors import PyMongoError

from second_brain_database.database import db_manager
from second_brain_database.managers import security_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.team_audit_manager import team_audit_manager
from second_brain_database.models.workspace_models import WorkspaceDocument, WorkspaceMember

# Import SBD token system (assuming it exists)
try:
    from second_brain_database.sbd_tokens import sbd_token_system
except ImportError:
    sbd_token_system = None

logger = get_logger(prefix="[TeamWalletManager]")

# --- Custom Exception Hierarchy for Team Wallets ---


class TeamWalletError(Exception):
    """Base exception for team wallet-related errors."""

    def __init__(self, message: str, error_code: str = "TEAM_WALLET_ERROR", context: Dict[str, Any] = None):
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}


class WorkspaceNotFound(TeamWalletError):
    """Raised when a workspace is not found."""

    def __init__(self, message: str = "Workspace not found."):
        super().__init__(message, "WORKSPACE_NOT_FOUND")


class InsufficientPermissions(TeamWalletError):
    """Raised when a user lacks the required permissions for an operation."""

    def __init__(self, message: str = "You do not have sufficient permissions to perform this action."):
        super().__init__(message, "INSUFFICIENT_PERMISSIONS")


class AccountFrozen(TeamWalletError):
    """Raised when trying to perform operations on a frozen account."""

    def __init__(self, message: str = "Team account is currently frozen.", context: Dict[str, Any] = None):
        super().__init__(message, "ACCOUNT_FROZEN", context)


class InsufficientBalance(TeamWalletError):
    """Raised when there are insufficient tokens for a transaction."""

    def __init__(self, message: str = "Insufficient balance in team account."):
        super().__init__(message, "INSUFFICIENT_BALANCE")


class TokenRequestNotFound(TeamWalletError):
    """Raised when a token request is not found."""

    def __init__(self, message: str = "Token request not found.", context: Dict[str, Any] = None):
        super().__init__(message, "TOKEN_REQUEST_NOT_FOUND", context)


class ValidationError(TeamWalletError):
    """Raised when request validation fails."""

    def __init__(self, message: str, context: Dict[str, Any] = None):
        super().__init__(message, "VALIDATION_ERROR", context)


class RateLimitExceeded(TeamWalletError):
    """Raised when rate limits are exceeded."""

    def __init__(self, message: str, context: Dict[str, Any] = None):
        super().__init__(message, "RATE_LIMIT_EXCEEDED", context)


class TransactionError(TeamWalletError):
    """Raised when a transaction fails."""

    def __init__(self, message: str, context: Dict[str, Any] = None):
        super().__init__(message, "TRANSACTION_ERROR", context)


class TeamWalletManager:
    """
    Manages all business logic for team SBD wallet functionality.
    """

    def __init__(self, db_manager_instance: Any = None, sbd_system: Any = None):
        """
        Initialize TeamWalletManager with dependency injection.
        Args:
            db_manager_instance: Database manager for data operations.
            sbd_system: SBD token system for blockchain operations.
        """
        self.db = db_manager_instance or db_manager
        self.sbd_system = sbd_system or sbd_token_system
        self.logger = logger
        self.logger.debug("TeamWalletManager initialized.")

    @property
    def workspaces_collection(self):
        """Lazy-loads the workspaces collection."""
        return self.db.get_collection("workspaces")

    @property
    def team_token_requests_collection(self):
        """Lazy-loads the team token requests collection."""
        return self.db.get_collection("team_token_requests")

    @property
    def team_transactions_collection(self):
        """Lazy-loads the team transactions collection."""
        return self.db.get_collection("team_transactions")

    @property
    def team_audit_log_collection(self):
        """Lazy-loads the team audit log collection."""
        return self.db.get_collection("team_audit_log")

    # --- Core Wallet Management Methods ---

    async def initialize_team_wallet(self, workspace_id: str, admin_user_id: str, session=None) -> Dict[str, Any]:
        """
        Initialize SBD wallet for a team workspace.

        Creates a virtual account username and sets up initial permissions.
        Only workspace admins can initialize the wallet.
        """
        self.logger.info(f"Initializing team wallet for workspace {workspace_id} by admin {admin_user_id}")

        # Verify admin permissions
        workspace = await self._find_workspace_if_admin(workspace_id, admin_user_id)

        # Check if wallet already initialized
        if workspace.get("sbd_account", {}).get("account_username"):
            raise TeamWalletError("Team wallet already initialized", "WALLET_ALREADY_EXISTS")

        # Generate unique account username
        account_username = f"team_{workspace_id}_{uuid.uuid4().hex[:8]}"

        # Set up initial permissions (admin gets full access, others get no spending by default)
        spending_permissions = {}
        for member in workspace["members"]:
            user_id = member["user_id"]
            if member["role"] == "admin":
                spending_permissions[user_id] = {
                    "can_spend": True,
                    "spending_limit": -1,  # Unlimited for admins
                    "updated_by": admin_user_id,
                    "updated_at": datetime.now(timezone.utc),
                }
            else:
                spending_permissions[user_id] = {
                    "can_spend": False,
                    "spending_limit": 0,
                    "updated_by": admin_user_id,
                    "updated_at": datetime.now(timezone.utc),
                }

        # Update workspace with wallet initialization using transaction safety
        update_data = {
            "sbd_account.account_username": account_username,
            "sbd_account.spending_permissions": spending_permissions,
            "updated_at": datetime.now(timezone.utc),
        }

        result = await self.workspaces_collection.update_one(
            {"workspace_id": workspace_id}, {"$set": update_data}, session=session
        )

        if result.modified_count == 0:
            raise TeamWalletError("Failed to initialize team wallet")

        # Log audit event (outside transaction for audit integrity)
        try:
            await team_audit_manager.log_permission_change_audit(
                team_id=workspace_id,
                admin_user_id=admin_user_id,
                admin_username="admin",  # TODO: Get actual username
                action="wallet_initialized",
                member_permissions=spending_permissions,
                session=session,
            )
        except Exception as audit_error:
            self.logger.warning(f"Failed to log audit for wallet initialization: {audit_error}")
            # Don't fail the operation for audit logging issues

        self.logger.info(f"Team wallet initialized for workspace {workspace_id}: {account_username}")
        return {
            "workspace_id": workspace_id,
            "account_username": account_username,
            "spending_permissions": spending_permissions,
            "initialized_at": datetime.now(timezone.utc),
        }

    async def get_team_wallet_info(self, workspace_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive team wallet information including balance and permissions.
        """
        workspace = await self._find_workspace_if_member(workspace_id, user_id)

        sbd_account = workspace.get("sbd_account", {})
        if not sbd_account.get("account_username"):
            raise TeamWalletError("Team wallet not initialized", "WALLET_NOT_INITIALIZED")

        # Get current balance from SBD system
        try:
            balance = await self._get_team_balance(sbd_account["account_username"])
        except Exception as e:
            self.logger.warning(f"Failed to get balance for team {workspace_id}: {e}")
            balance = 0

        # Get recent transactions
        recent_transactions = await self._get_recent_team_transactions(workspace_id, limit=10)

        # Get user permissions
        user_permissions = sbd_account.get("spending_permissions", {}).get(user_id, {})

        return {
            "workspace_id": workspace_id,
            "account_username": sbd_account["account_username"],
            "balance": balance,
            "is_frozen": sbd_account.get("is_frozen", False),
            "frozen_by": sbd_account.get("frozen_by"),
            "frozen_at": sbd_account.get("frozen_at"),
            "user_permissions": user_permissions,
            "notification_settings": sbd_account.get("notification_settings", {}),
            "recent_transactions": recent_transactions,
        }

    # --- Token Request Management ---

    async def create_token_request(
        self,
        workspace_id: str,
        user_id: str,
        amount: int,
        reason: str,
        request_context: Dict[str, Any] = None,
        session: ClientSession = None,
    ) -> Dict[str, Any]:
        """
        Create a token request from team account.
        """
        workspace = await self._find_workspace_if_member(workspace_id, user_id)

        sbd_account = workspace.get("sbd_account", {})
        if not sbd_account.get("account_username"):
            raise TeamWalletError("Team wallet not initialized", "WALLET_NOT_INITIALIZED")

        if sbd_account.get("is_frozen"):
            raise AccountFrozen("Team account is frozen")

        # Validate amount and reason
        if amount <= 0:
            raise ValidationError("Amount must be positive")
        if len(reason.strip()) < 5:
            raise ValidationError("Reason must be at least 5 characters")

        # Check auto-approval threshold (configurable per workspace)
        auto_approval_threshold = workspace.get("settings", {}).get("auto_approval_threshold", 100)

        auto_approved = amount <= auto_approval_threshold
        status = "approved" if auto_approved else "pending"
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)  # 7 days expiry

        # Create request document
        request_doc = {
            "request_id": f"req_{uuid.uuid4().hex}",
            "workspace_id": workspace_id,
            "requester_user_id": user_id,
            "amount": amount,
            "reason": reason.strip(),
            "status": status,
            "auto_approved": auto_approved,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "updated_at": datetime.now(timezone.utc),
        }

        await self.team_token_requests_collection.insert_one(request_doc, session=session)

        # If auto-approved, process immediately
        if auto_approved:
            await self._process_token_request(request_doc["request_id"], user_id, request_context, session)

        # Log audit event (outside transaction for audit integrity)
        try:
            await team_audit_manager.log_sbd_transaction_audit(
                team_id=workspace_id,
                transaction_id=request_doc["request_id"],
                transaction_type="token_request_created",
                amount=amount,
                from_account=sbd_account["account_username"],
                to_account="pending",  # Not yet assigned
                team_member_id=user_id,
                team_member_username="member",  # TODO: Get actual username
                transaction_context=request_context,
                session=session,
            )
        except Exception as audit_error:
            self.logger.warning(f"Failed to log audit for token request: {audit_error}")
            # Don't fail the operation for audit logging issues

        return request_doc

    async def review_token_request(
        self, request_id: str, admin_id: str, action: str, comments: str = None, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Review a token request (approve or deny).
        """
        # Find the request
        request_doc = await self.team_token_requests_collection.find_one({"request_id": request_id})
        if not request_doc:
            raise TokenRequestNotFound()

        workspace_id = request_doc["workspace_id"]

        # Verify admin permissions
        await self._find_workspace_if_admin(workspace_id, admin_id)

        if request_doc["status"] != "pending":
            raise ValidationError("Request is not in pending status")

        if request_doc["expires_at"] < datetime.now(timezone.utc):
            raise ValidationError("Request has expired")

        # Update request status
        new_status = "approved" if action == "approve" else "denied"
        update_data = {
            "status": new_status,
            "reviewed_by": admin_id,
            "admin_comments": comments,
            "reviewed_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        await self.team_token_requests_collection.update_one({"request_id": request_id}, {"$set": update_data})

        # If approved, process the transfer
        processed_at = None
        if action == "approve":
            processed_at = await self._process_token_request(request_id, admin_id, request_context)

        # Log audit event
        await team_audit_manager.log_sbd_transaction_audit(
            team_id=workspace_id,
            transaction_id=request_id,
            transaction_type=f"token_request_{action}d",
            amount=request_doc["amount"],
            from_account="pending",  # From pending request
            to_account=request_doc["requester_user_id"] if action == "approve" else "denied",
            team_member_id=admin_id,
            team_member_username="admin",  # TODO: Get actual username
            transaction_context=request_context,
        )

        return {
            "request_id": request_id,
            "action": action,
            "status": new_status,
            "reviewed_by": admin_id,
            "processed_at": processed_at,
            "amount": request_doc["amount"],
        }

    async def get_pending_token_requests(self, workspace_id: str, admin_id: str) -> List[Dict[str, Any]]:
        """
        Get all pending token requests for a workspace.

        Only workspace admins can view pending requests.
        """
        # Verify admin permissions
        await self._find_workspace_if_admin(workspace_id, admin_id)

        # Query for pending requests
        cursor = self.team_token_requests_collection.find(
            {"workspace_id": workspace_id, "status": "pending", "expires_at": {"$gt": datetime.now(timezone.utc)}}
        ).sort("created_at", -1)

        pending_requests = []
        async for request_doc in cursor:
            pending_requests.append(
                {
                    "request_id": request_doc["request_id"],
                    "requester_username": request_doc.get("requester_username", "Unknown"),
                    "amount": request_doc["amount"],
                    "reason": request_doc["reason"],
                    "status": request_doc["status"],
                    "auto_approved": request_doc.get("auto_approved", False),
                    "created_at": request_doc["created_at"].isoformat(),
                    "expires_at": request_doc["expires_at"].isoformat(),
                    "admin_comments": request_doc.get("admin_comments"),
                }
            )

        return pending_requests

    # --- Permission Management ---

    async def update_spending_permissions(
        self, workspace_id: str, admin_id: str, user_id: str, permissions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update spending permissions for a team member.
        """
        workspace = await self._find_workspace_if_admin(workspace_id, admin_id)

        # Verify target user is a member
        if not any(m["user_id"] == user_id for m in workspace["members"]):
            raise TeamWalletError("User is not a team member", "USER_NOT_MEMBER")

        # Update permissions
        update_path = f"sbd_account.spending_permissions.{user_id}"
        update_data = {
            update_path: {**permissions, "updated_by": admin_id, "updated_at": datetime.now(timezone.utc)},
            "updated_at": datetime.now(timezone.utc),
        }

        result = await self.workspaces_collection.update_one({"workspace_id": workspace_id}, {"$set": update_data})

        if result.modified_count == 0:
            raise TeamWalletError("Failed to update spending permissions")

        # Log audit event
        await team_audit_manager.log_permission_change_audit(
            team_id=workspace_id,
            admin_user_id=admin_id,
            admin_username="admin",  # TODO: Get actual username
            action="permissions_updated",
            member_permissions={user_id: permissions},
        )

        return {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "permissions": permissions,
            "updated_by": admin_id,
            "updated_at": datetime.now(timezone.utc),
        }

    # --- Account Freeze/Unfreeze ---

    async def freeze_team_account(self, workspace_id: str, admin_id: str, reason: str) -> Dict[str, Any]:
        """
        Freeze the team account to prevent spending.
        """
        workspace = await self._find_workspace_if_admin(workspace_id, admin_id)

        if workspace.get("sbd_account", {}).get("is_frozen"):
            raise TeamWalletError("Account is already frozen")

        update_data = {
            "sbd_account.is_frozen": True,
            "sbd_account.frozen_by": admin_id,
            "sbd_account.frozen_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        result = await self.workspaces_collection.update_one({"workspace_id": workspace_id}, {"$set": update_data})

        if result.modified_count == 0:
            raise TeamWalletError("Failed to freeze account")

        # Log audit event
        await team_audit_manager.log_account_freeze_audit(
            team_id=workspace_id,
            admin_user_id=admin_id,
            admin_username="admin",  # TODO: Get actual username
            action="freeze",
            reason=reason,
        )

        return {
            "workspace_id": workspace_id,
            "is_frozen": True,
            "frozen_by": admin_id,
            "frozen_at": datetime.now(timezone.utc),
            "reason": reason,
        }

    async def unfreeze_team_account(self, workspace_id: str, admin_id: str) -> Dict[str, Any]:
        """
        Unfreeze the team account to allow spending.
        """
        workspace = await self._find_workspace_if_admin(workspace_id, admin_id)

        if not workspace.get("sbd_account", {}).get("is_frozen"):
            raise TeamWalletError("Account is not frozen")

        update_data = {
            "sbd_account.is_frozen": False,
            "sbd_account.frozen_by": None,
            "sbd_account.frozen_at": None,
            "updated_at": datetime.now(timezone.utc),
        }

        result = await self.workspaces_collection.update_one({"workspace_id": workspace_id}, {"$set": update_data})

        if result.modified_count == 0:
            raise TeamWalletError("Failed to unfreeze account")

        # Log audit event
        await team_audit_manager.log_account_freeze_audit(
            team_id=workspace_id,
            admin_user_id=admin_id,
            admin_username="admin",  # TODO: Get actual username
            action="unfreeze",
            reason="Administrative unfreeze",
        )

        return {
            "workspace_id": workspace_id,
            "is_frozen": False,
            "unfrozen_by": admin_id,
            "unfrozen_at": datetime.now(timezone.utc),
        }

    # --- Private Helper Methods ---

    async def _find_workspace_if_member(self, workspace_id: str, user_id: str) -> Dict[str, Any]:
        """Find workspace and verify user is a member."""
        workspace = await self.workspaces_collection.find_one(
            {"workspace_id": workspace_id, "members.user_id": user_id}
        )
        if not workspace:
            if await self.workspaces_collection.count_documents({"workspace_id": workspace_id}) > 0:
                raise InsufficientPermissions()
            else:
                raise WorkspaceNotFound()
        return workspace

    async def _find_workspace_if_admin(self, workspace_id: str, user_id: str) -> Dict[str, Any]:
        """Find workspace and verify user is an admin."""
        workspace = await self.workspaces_collection.find_one({"workspace_id": workspace_id})
        if not workspace:
            raise WorkspaceNotFound()

        user_role = self._get_user_role(user_id, workspace)
        if user_role != "admin":
            raise InsufficientPermissions()

        return workspace

    def _get_user_role(self, user_id: str, workspace: Dict[str, Any]) -> Optional[str]:
        """Get user's role in workspace."""
        for member in workspace.get("members", []):
            if member["user_id"] == user_id:
                return member["role"]
        return None

    async def _get_team_balance(self, account_username: str) -> int:
        """Get current balance from SBD system."""
        if not self.sbd_system:
            return 0
        try:
            return await self.sbd_system.get_balance(account_username)
        except Exception:
            return 0

    async def _get_recent_team_transactions(self, workspace_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent transactions for the team."""
        cursor = (
            self.team_transactions_collection.find({"workspace_id": workspace_id}).sort("created_at", -1).limit(limit)
        )

        transactions = []
        async for doc in cursor:
            transactions.append(
                {
                    "transaction_id": doc.get("transaction_id"),
                    "type": doc.get("type"),
                    "amount": doc.get("amount"),
                    "from_user": doc.get("from_user"),
                    "to_user": doc.get("to_user"),
                    "timestamp": doc.get("created_at"),
                    "description": doc.get("description", ""),
                }
            )

        return transactions

    async def _process_token_request(
        self, request_id: str, processed_by: str, request_context: Dict[str, Any] = None, session: ClientSession = None
    ) -> datetime:
        """
        Process an approved token request by transferring tokens.
        """
        request_doc = await self.team_token_requests_collection.find_one({"request_id": request_id}, session=session)
        if not request_doc or request_doc["status"] != "approved":
            raise TeamWalletError("Invalid request for processing")

        workspace_id = request_doc["workspace_id"]
        workspace = await self.workspaces_collection.find_one({"workspace_id": workspace_id}, session=session)
        account_username = workspace["sbd_account"]["account_username"]

        # Get requester info
        requester_id = request_doc["requester_user_id"]
        amount = request_doc["amount"]

        # Perform the transfer
        processed_at = datetime.now(timezone.utc)

        # Here we would integrate with the actual SBD transfer system
        # For now, we'll just log the transaction
        transaction_doc = {
            "transaction_id": f"txn_{uuid.uuid4().hex}",
            "workspace_id": workspace_id,
            "type": "transfer",
            "amount": amount,
            "from_account": account_username,
            "to_user": requester_id,
            "processed_by": processed_by,
            "description": f"Token request fulfillment: {request_doc['reason']}",
            "created_at": processed_at,
            "request_id": request_id,
        }

        await self.team_transactions_collection.insert_one(transaction_doc, session=session)

        # Update request as processed
        await self.team_token_requests_collection.update_one(
            {"request_id": request_id},
            {"$set": {"processed_at": processed_at, "updated_at": processed_at}},
            session=session,
        )

        return processed_at

    # --- Emergency Recovery Features ---

    async def emergency_unfreeze_account(
        self, workspace_id: str, backup_admin_id: str, emergency_reason: str, session: ClientSession = None
    ) -> Dict[str, Any]:
        """
        Emergency unfreeze mechanism for backup admins when primary admins are unavailable.

        This is a critical recovery feature that allows designated backup admins to unfreeze
        accounts in emergency situations.
        """
        workspace = await self.workspaces_collection.find_one({"workspace_id": workspace_id}, session=session)
        if not workspace:
            raise WorkspaceNotFound()

        # Check if user is a designated backup admin
        backup_admins = workspace.get("settings", {}).get("backup_admins", [])
        if backup_admin_id not in backup_admins:
            raise InsufficientPermissions("User is not authorized as backup admin")

        if not workspace.get("sbd_account", {}).get("is_frozen"):
            raise TeamWalletError("Account is not frozen")

        # Emergency unfreeze
        update_data = {
            "sbd_account.is_frozen": False,
            "sbd_account.frozen_by": None,
            "sbd_account.frozen_at": None,
            "sbd_account.emergency_unfrozen": True,
            "sbd_account.emergency_unfrozen_by": backup_admin_id,
            "sbd_account.emergency_unfrozen_at": datetime.now(timezone.utc),
            "sbd_account.emergency_reason": emergency_reason,
            "updated_at": datetime.now(timezone.utc),
        }

        result = await self.workspaces_collection.update_one(
            {"workspace_id": workspace_id}, {"$set": update_data}, session=session
        )

        if result.modified_count == 0:
            raise TeamWalletError("Failed to emergency unfreeze account")

        # Log audit event
        try:
            await team_audit_manager.log_account_freeze_audit(
                team_id=workspace_id,
                admin_user_id=backup_admin_id,
                admin_username="backup_admin",  # TODO: Get actual username
                action="emergency_unfreeze",
                reason=f"EMERGENCY: {emergency_reason}",
                session=session,
            )
        except Exception as audit_error:
            self.logger.warning(f"Failed to log audit for emergency unfreeze: {audit_error}")

        self.logger.warning(
            f"EMERGENCY UNFREEZE: Team account {workspace_id} unfrozen by backup admin {backup_admin_id}"
        )

        return {
            "workspace_id": workspace_id,
            "is_frozen": False,
            "emergency_unfrozen": True,
            "emergency_unfrozen_by": backup_admin_id,
            "emergency_reason": emergency_reason,
            "unfrozen_at": datetime.now(timezone.utc),
        }

    async def designate_backup_admin(
        self, workspace_id: str, admin_id: str, backup_admin_id: str, session: ClientSession = None
    ) -> Dict[str, Any]:
        """
        Designate a backup admin for emergency recovery operations.

        Only primary admins can designate backup admins.
        """
        workspace = await self._find_workspace_if_admin(workspace_id, admin_id)

        # Verify backup admin is a workspace member
        if not any(m["user_id"] == backup_admin_id for m in workspace["members"]):
            raise TeamWalletError("Backup admin must be a workspace member", "USER_NOT_MEMBER")

        # Add to backup admins list
        backup_admins = workspace.get("settings", {}).get("backup_admins", [])
        if backup_admin_id in backup_admins:
            raise TeamWalletError("User is already designated as backup admin")

        backup_admins.append(backup_admin_id)

        update_data = {"settings.backup_admins": backup_admins, "updated_at": datetime.now(timezone.utc)}

        result = await self.workspaces_collection.update_one(
            {"workspace_id": workspace_id}, {"$set": update_data}, session=session
        )

        if result.modified_count == 0:
            raise TeamWalletError("Failed to designate backup admin")

        # Log audit event
        try:
            await team_audit_manager.log_permission_change_audit(
                team_id=workspace_id,
                admin_user_id=admin_id,
                admin_username="admin",  # TODO: Get actual username
                action="backup_admin_designated",
                member_permissions={"backup_admin": backup_admin_id},
                session=session,
            )
        except Exception as audit_error:
            self.logger.warning(f"Failed to log audit for backup admin designation: {audit_error}")

        return {
            "workspace_id": workspace_id,
            "backup_admin_id": backup_admin_id,
            "designated_by": admin_id,
            "designated_at": datetime.now(timezone.utc),
        }

    async def remove_backup_admin(
        self, workspace_id: str, admin_id: str, backup_admin_id: str, session: ClientSession = None
    ) -> Dict[str, Any]:
        """
        Remove a backup admin designation.

        Only primary admins can remove backup admin designations.
        """
        workspace = await self._find_workspace_if_admin(workspace_id, admin_id)

        backup_admins = workspace.get("settings", {}).get("backup_admins", [])
        if backup_admin_id not in backup_admins:
            raise TeamWalletError("User is not designated as backup admin")

        backup_admins.remove(backup_admin_id)

        update_data = {"settings.backup_admins": backup_admins, "updated_at": datetime.now(timezone.utc)}

        result = await self.workspaces_collection.update_one(
            {"workspace_id": workspace_id}, {"$set": update_data}, session=session
        )

        if result.modified_count == 0:
            raise TeamWalletError("Failed to remove backup admin")

        # Log audit event
        try:
            await team_audit_manager.log_permission_change_audit(
                team_id=workspace_id,
                admin_user_id=admin_id,
                admin_username="admin",  # TODO: Get actual username
                action="backup_admin_removed",
                member_permissions={"removed_backup_admin": backup_admin_id},
                session=session,
            )
        except Exception as audit_error:
            self.logger.warning(f"Failed to log audit for backup admin removal: {audit_error}")

        return {
            "workspace_id": workspace_id,
            "removed_backup_admin_id": backup_admin_id,
            "removed_by": admin_id,
            "removed_at": datetime.now(timezone.utc),
        }

    # --- Compliance Endpoints ---

    async def get_team_audit_trail(
        self, workspace_id: str, admin_id: str, start_date: datetime = None, end_date: datetime = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail for compliance reporting.

        Only admins can access audit trails.
        """
        await self._find_workspace_if_admin(workspace_id, admin_id)

        return await team_audit_manager.get_team_audit_trail(
            team_id=workspace_id, start_date=start_date, end_date=end_date, limit=limit
        )

    async def generate_compliance_report(
        self,
        workspace_id: str,
        admin_id: str,
        report_type: str = "json",
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> Dict[str, Any]:
        """
        Generate compliance report for the team.

        Only admins can generate compliance reports.
        """
        await self._find_workspace_if_admin(workspace_id, admin_id)

        return await team_audit_manager.generate_compliance_report(
            team_id=workspace_id, report_type=report_type, start_date=start_date, end_date=end_date
        )

    async def verify_audit_integrity(self, workspace_id: str, admin_id: str, audit_id: str) -> bool:
        """
        Verify integrity of an audit trail record.

        Only admins can verify audit integrity.
        """
        await self._find_workspace_if_admin(workspace_id, admin_id)

        return await team_audit_manager.verify_audit_integrity(audit_id)


# Global TeamWalletManager instance
team_wallet_manager = TeamWalletManager()
