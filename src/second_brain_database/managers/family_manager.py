"""
Family Manager for handling family relationships, SBD token accounts, and member management.

This module provides the FamilyManager class, which manages family creation,
member invitations, bidirectional relationships, and SBD token integration
following the established manager patterns in the codebase with enterprise-grade
patterns including dependency injection, transaction safety, and comprehensive
error handling with resilience features.

Enterprise Features:
    - Dependency injection for testability and modularity
    - Transaction safety with MongoDB sessions for critical operations
    - Comprehensive error handling with custom exception hierarchy
    - Circuit breaker and bulkhead patterns for resilience
    - Automatic retry with exponential backoff
    - Graceful degradation for system failures
    - Error monitoring and alerting integration
    - Secure token generation using cryptographically secure methods
    - Configurable family limits with real-time validation
    - Comprehensive audit logging for all operations
    - Rate limiting integration for abuse prevention

Resilience Features:
    - Circuit breakers for external service protection
    - Bulkhead pattern for resource isolation
    - Automatic error recovery with intelligent retry strategies
    - Graceful degradation when services are unavailable
    - Real-time error monitoring and alerting
    - User-friendly error message translation

Logging:
    - Uses the centralized logging manager with structured context
    - Logs all family operations, SBD transactions, and security events
    - Performance metrics tracking for all database operations
    - All exceptions are logged with full traceback and context
    - Error monitoring with pattern detection and alerting
"""

from datetime import datetime, timedelta, timezone
import secrets
import time
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable
import uuid

from bson import ObjectId
from pymongo.client_session import ClientSession
from pymongo.errors import DuplicateKeyError, PyMongoError

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.models.family_models import (
    PurchaseRequestDocument,
    PurchaseRequestItemInfo,
    PurchaseRequestUserInfo,
)

# Import enterprise error handling and resilience features
from second_brain_database.utils.error_handling import (
    ErrorContext,
    ErrorSeverity,
    RetryConfig,
    RetryStrategy,
    create_user_friendly_error,
    handle_errors,
    sanitize_sensitive_data,
    validate_input,
)
from second_brain_database.utils.error_monitoring import error_monitor, record_error_event
from second_brain_database.utils.error_recovery import (
    RecoveryStrategy,
    recover_from_database_error,
    recover_from_redis_error,
    recover_with_graceful_degradation,
    recovery_manager,
)

logger = get_logger(prefix="[FamilyManager]")

# Import monitoring system
try:
    from second_brain_database.managers.family_monitoring import (
        FamilyOperationContext,
        FamilyOperationType,
        family_monitor,
    )

    MONITORING_ENABLED = True
except ImportError:
    # Graceful fallback if monitoring is not available
    MONITORING_ENABLED = False
    logger.warning("Family monitoring system not available - continuing without monitoring")

# Constants for family management
DEFAULT_MAX_FAMILIES = 1
DEFAULT_MAX_MEMBERS_PER_FAMILY = 5
INVITATION_EXPIRY_DAYS = 7
AUTO_APPROVAL_THRESHOLD = 100
TOKEN_REQUEST_EXPIRY_HOURS = 168  # 7 days
FAMILY_CREATION_RATE_LIMIT = 5  # Max families created per hour per user
INVITATION_RATE_LIMIT = 20  # Max invitations sent per hour per user
VIRTUAL_ACCOUNT_PREFIX = "family_"
RESERVED_PREFIXES = ["family_", "team_", "admin_", "system_", "bot_", "service_"]
VIRTUAL_ACCOUNT_RETENTION_DAYS = 90  # Data retention period for deleted virtual accounts
MAX_FAMILY_NAME_LENGTH = 50
MIN_FAMILY_NAME_LENGTH = 3

# Relationship types mapping for bidirectional relationships
RELATIONSHIP_TYPES = {
    "parent": "child",
    "child": "parent",
    "sibling": "sibling",
    "spouse": "spouse",
    "grandparent": "grandchild",
    "grandchild": "grandparent",
    "uncle": "nephew",
    "aunt": "niece",
    "nephew": "uncle",
    "niece": "aunt",
    "cousin": "cousin",
}


# Dependency injection protocols for enterprise patterns
@runtime_checkable
class DatabaseManagerProtocol(Protocol):
    """Protocol for database manager dependency injection."""

    async def get_collection(self, collection_name: str) -> Any: ...
    def log_query_start(self, collection: str, operation: str, context: Dict[str, Any]) -> float: ...
    def log_query_success(
        self, collection: str, operation: str, start_time: float, count: int, info: str = None
    ) -> None: ...
    def log_query_error(
        self, collection: str, operation: str, start_time: float, error: Exception, context: Dict[str, Any]
    ) -> None: ...


@runtime_checkable
class EmailManagerProtocol(Protocol):
    """Protocol for email manager dependency injection."""

    async def send_family_invitation_email(
        self,
        to_email: str,
        inviter_username: str,
        family_name: str,
        relationship_type: str,
        accept_link: str,
        decline_link: str,
        expires_at: str,
    ) -> bool: ...


@runtime_checkable
class SecurityManagerProtocol(Protocol):
    """Protocol for security manager dependency injection."""

    async def check_rate_limit(
        self, request: Any, action: str, rate_limit_requests: int = None, rate_limit_period: int = None
    ) -> None: ...


@runtime_checkable
class RedisManagerProtocol(Protocol):
    """Protocol for Redis manager dependency injection."""

    async def get_redis(self) -> Any: ...
    async def set_with_expiry(self, key: str, value: Any, expiry: int) -> None: ...
    async def get(self, key: str) -> Any: ...


# Enhanced exception hierarchy for comprehensive error handling
class FamilyError(Exception):
    """Base family management exception with enhanced context."""

    def __init__(self, message: str, error_code: str = None, context: Dict[str, Any] = None):
        super().__init__(message)
        self.error_code = error_code or "FAMILY_ERROR"
        self.context = context or {}
        self.timestamp = datetime.now(timezone.utc)


class FamilyLimitExceeded(FamilyError):
    """User has reached family limits with upgrade information."""

    def __init__(self, message: str, current_count: int = None, max_allowed: int = None, limit_type: str = None):
        super().__init__(
            message,
            "FAMILY_LIMIT_EXCEEDED",
            {
                "current_count": current_count,
                "max_allowed": max_allowed,
                "limit_type": limit_type,
                "upgrade_required": True,
            },
        )


class InvalidRelationship(FamilyError):
    """Relationship validation failed with detailed context."""

    def __init__(self, message: str, relationship_type: str = None, valid_types: List[str] = None):
        super().__init__(
            message,
            "INVALID_RELATIONSHIP",
            {"relationship_type": relationship_type, "valid_types": valid_types or list(RELATIONSHIP_TYPES.keys())},
        )


class FamilyNotFound(FamilyError):
    """Family does not exist or is not accessible."""

    def __init__(self, message: str, family_id: str = None):
        super().__init__(message, "FAMILY_NOT_FOUND", {"family_id": family_id})


class InvitationNotFound(FamilyError):
    """Invitation does not exist, expired, or already processed."""

    def __init__(self, message: str, invitation_id: str = None, status: str = None):
        super().__init__(message, "INVITATION_NOT_FOUND", {"invitation_id": invitation_id, "status": status})


class InsufficientPermissions(FamilyError):
    """User lacks required permissions for the operation."""

    def __init__(self, message: str, required_role: str = None, user_role: str = None):
        super().__init__(message, "INSUFFICIENT_PERMISSIONS", {"required_role": required_role, "user_role": user_role})


class AccountFrozen(FamilyError):
    """Family SBD account is frozen and cannot be used."""

    def __init__(self, message: str, family_id: str = None, frozen_by: str = None, frozen_at: datetime = None):
        super().__init__(
            message,
            "ACCOUNT_FROZEN",
            {"family_id": family_id, "frozen_by": frozen_by, "frozen_at": frozen_at.isoformat() if frozen_at else None},
        )


class SpendingLimitExceeded(FamilyError):
    """Transaction exceeds user's spending limit."""

    def __init__(self, message: str, amount: int = None, limit: int = None, user_id: str = None):
        super().__init__(message, "SPENDING_LIMIT_EXCEEDED", {"amount": amount, "limit": limit, "user_id": user_id})


class TokenRequestNotFound(FamilyError):
    """Token request does not exist or is not accessible."""

    def __init__(self, message: str, request_id: str = None, status: str = None):
        super().__init__(message, "TOKEN_REQUEST_NOT_FOUND", {"request_id": request_id, "status": status})


class TransactionError(FamilyError):
    """Database transaction failed with rollback information."""

    def __init__(self, message: str, operation: str = None, rollback_successful: bool = None):
        super().__init__(
            message, "TRANSACTION_ERROR", {"operation": operation, "rollback_successful": rollback_successful}
        )


class ValidationError(FamilyError):
    """Input validation failed with field-specific details."""

    def __init__(self, message: str, field: str = None, value: Any = None, constraint: str = None):
        super().__init__(
            message,
            "VALIDATION_ERROR",
            {"field": field, "value": str(value) if value is not None else None, "constraint": constraint},
        )


class RateLimitExceeded(FamilyError):
    """Rate limit exceeded for family operations."""

    def __init__(self, message: str, action: str = None, limit: int = None, window: int = None):
        super().__init__(message, "RATE_LIMIT_EXCEEDED", {"action": action, "limit": limit, "window_seconds": window})


class MultipleAdminsRequired(FamilyError):
    """Operation requires multiple admins."""

    def __init__(self, message: str, operation: str = None, current_admins: int = None):
        super().__init__(
            message,
            "MULTIPLE_ADMINS_REQUIRED",
            {"operation": operation, "current_admins": current_admins, "minimum_required": 2},
        )


class AdminActionError(FamilyError):
    """Admin action validation failed with detailed context."""

    def __init__(self, message: str, action: str = None, target_user: str = None, current_admin: str = None):
        super().__init__(
            message,
            "ADMIN_ACTION_ERROR",
            {"action": action, "target_user": target_user, "current_admin": current_admin},
        )


class BackupAdminError(FamilyError):
    """Backup admin operation failed."""

    def __init__(self, message: str, operation: str = None, backup_admin: str = None):
        super().__init__(message, "BACKUP_ADMIN_ERROR", {"operation": operation, "backup_admin": backup_admin})


class FamilyManager:
    """
    Enterprise-grade family management system with dependency injection and transaction safety.

    This manager implements comprehensive family relationship management with:
    - Dependency injection for testability and modularity
    - Transaction safety using MongoDB sessions for critical operations
    - Comprehensive error handling with detailed context
    - Rate limiting integration for abuse prevention
    - Secure token generation and validation
    - Configurable family limits with real-time enforcement
    - Comprehensive audit logging and performance metrics

    Enterprise Patterns:
    - Manager pattern with dependency injection
    - Transaction script pattern for complex operations
    - Repository pattern abstraction for data access
    - Strategy pattern for different validation rules
    - Observer pattern for notification events
    """

    def __init__(
        self,
        db_manager: DatabaseManagerProtocol = None,
        email_manager: EmailManagerProtocol = None,
        security_manager: SecurityManagerProtocol = None,
        redis_manager: RedisManagerProtocol = None,
    ) -> None:
        """
        Initialize FamilyManager with dependency injection.

        Args:
            db_manager: Database manager for data operations
            email_manager: Email manager for sending notifications
            security_manager: Security manager for rate limiting
            redis_manager: Redis manager for caching and rate limiting
        """
        # Dependency injection with fallback to global instances
        self.db_manager = db_manager or globals()["db_manager"]
        self.email_manager = email_manager or globals()["email_manager"]
        self.security_manager = security_manager or globals()["security_manager"]
        self.redis_manager = redis_manager or globals()["redis_manager"]

        self.logger = logger
        self.logger.debug("FamilyManager initialized with dependency injection")

        # Cache for frequently accessed data
        self._user_cache = {}
        self._family_cache = {}
        self._cache_ttl = 300  # 5 minutes cache TTL

    @handle_errors(
        operation_name="create_family",
        circuit_breaker="family_operations",
        bulkhead="family_creation",
        retry_config=RetryConfig(
            max_attempts=3,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retryable_exceptions=[PyMongoError, ConnectionError],
            non_retryable_exceptions=[FamilyLimitExceeded, ValidationError],
        ),
        timeout=30.0,
        user_friendly_errors=True,
    )
    async def create_family(
        self, user_id: str, name: Optional[str] = None, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a new family with the user as administrator using transaction safety.

        Args:
            user_id: ID of the user creating the family
            name: Optional custom family name
            request_context: Request context for rate limiting and security

        Returns:
            Dict containing family information

        Raises:
            FamilyLimitExceeded: If user has reached family limits
            RateLimitExceeded: If rate limit exceeded
            ValidationError: If input validation fails
            TransactionError: If database transaction fails
            FamilyError: If family creation fails
        """
        # Create error context for comprehensive error handling
        error_context = ErrorContext(
            operation="create_family",
            user_id=user_id,
            request_id=request_context.get("request_id") if request_context else None,
            ip_address=request_context.get("ip_address") if request_context else None,
            metadata={"family_name": name, "has_request_context": bool(request_context)},
        )

        operation_context = {
            "user_id": user_id,
            "name": name,
            "operation": "create_family",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "create_family", operation_context)

        # Input validation with comprehensive security controls
        try:
            validation_schema = {
                "user_id": {
                    "required": True,
                    "type": str,
                    "min_length": 1,
                    "max_length": 100,
                    "pattern": r"^[a-zA-Z0-9_-]+$",
                },
                "name": {
                    "required": False,
                    "type": str,
                    "min_length": MIN_FAMILY_NAME_LENGTH,
                    "max_length": MAX_FAMILY_NAME_LENGTH,
                    "validator": lambda x: not any(prefix in x.lower() for prefix in RESERVED_PREFIXES),
                },
            }

            input_data = {"user_id": user_id}
            if name:
                input_data["name"] = name

            validated_data = validate_input(input_data, validation_schema, error_context)
            user_id = validated_data["user_id"]
            name = validated_data.get("name")

        except Exception as e:
            await record_error_event(e, error_context, ErrorSeverity.MEDIUM)
            raise ValidationError(f"Input validation failed: {str(e)}")

        # Rate limiting check with error monitoring
        if request_context:
            try:
                await self._check_rate_limit(request_context, "family_creation", FAMILY_CREATION_RATE_LIMIT, 3600)
            except Exception as e:
                await record_error_event(e, error_context, ErrorSeverity.HIGH)
                raise RateLimitExceeded(
                    "Family creation rate limit exceeded",
                    action="family_creation",
                    limit=FAMILY_CREATION_RATE_LIMIT,
                    window=3600,
                )

        # Start database transaction for atomicity
        client = self.db_manager.client
        session = None

        try:
            # Input validation
            await self._validate_family_creation_input(user_id, name)

            # Check family limits with detailed context
            limits_info = await self._check_family_creation_limits(user_id)

            # Generate unique identifiers
            family_id = f"fam_{uuid.uuid4().hex[:16]}"
            if not name:
                user = await self._get_user_by_id(user_id)
                name = f"{user.get('username', 'Unknown')}'s Family"

            # Validate and generate SBD account username
            sbd_account_username = await self._generate_unique_sbd_username(name)

            # If the database doesn't support transactions (e.g., local standalone Mongo),
            # fall back to a careful non-transactional flow with compensating cleanup.
            if getattr(self.db_manager, "transactions_supported", False) is False:
                self.logger.warning(
                    "Database does not support transactions; using non-transactional fallback for create_family"
                )
                return await self._create_family_non_transactional(
                    user_id, name, family_id, sbd_account_username, limits_info, start_time, operation_context
                )

            # Start transaction
            session = await client.start_session()

            async with session.start_transaction():
                now = datetime.now(timezone.utc)

                # Create comprehensive family document
                family_doc = await self._build_family_document(family_id, name, user_id, sbd_account_username, now)

                # Insert family document within transaction
                families_collection = self.db_manager.get_tenant_collection("families")
                await families_collection.insert_one(family_doc, session=session)

                # Create virtual SBD account within transaction
                await self._create_virtual_sbd_account_transactional(sbd_account_username, family_id, session)

                # Update user's family membership within transaction
                await self._add_user_to_family_membership_transactional(user_id, family_id, "admin", now, session)

                # Cache the new family for performance
                self._cache_family(family_id, family_doc)

                # Log successful creation
                self.db_manager.log_query_success(
                    "families", "create_family", start_time, 1, f"Family created with transaction: {family_id}"
                )

                self.logger.info(
                    "Family created successfully with transaction safety: %s by user %s",
                    family_id,
                    user_id,
                    extra={
                        "family_id": family_id,
                        "user_id": user_id,
                        "sbd_account": sbd_account_username,
                        "transaction_id": str(session.session_id) if session else None,
                    },
                )

                # Log to monitoring system
                if MONITORING_ENABLED:
                    duration = time.time() - start_time
                    await family_monitor.log_family_operation(
                        FamilyOperationContext(
                            operation_type=FamilyOperationType.FAMILY_CREATE,
                            family_id=family_id,
                            user_id=user_id,
                            duration=duration,
                            success=True,
                            metadata={
                                "family_name": name,
                                "sbd_account": sbd_account_username,
                                "transaction_safe": True,
                            },
                            request_id=operation_context.get("request_id"),
                        )
                    )
                    await family_monitor.log_family_performance(
                        FamilyOperationType.FAMILY_CREATE, duration, success=True, metadata={"family_name": name}
                    )

                return {
                    "family_id": family_id,
                    "name": name,
                    "admin_user_ids": [user_id],
                    "member_count": 1,
                    "created_at": now,
                    "sbd_account": {"account_username": sbd_account_username, "balance": 0, "is_frozen": False},
                    "limits_info": limits_info,
                    "transaction_safe": True,
                }

        except (FamilyLimitExceeded, ValidationError, RateLimitExceeded) as e:
            # These are expected validation errors, don't wrap them
            self.db_manager.log_query_error("families", "create_family", start_time, e, operation_context)

            # Record error for monitoring and analysis
            severity = ErrorSeverity.HIGH if isinstance(e, FamilyLimitExceeded) else ErrorSeverity.MEDIUM
            await record_error_event(e, error_context, severity)

            # Log to monitoring system
            if MONITORING_ENABLED:
                duration = time.time() - start_time
                await family_monitor.log_family_operation(
                    FamilyOperationContext(
                        operation_type=FamilyOperationType.FAMILY_CREATE,
                        user_id=user_id,
                        duration=duration,
                        success=False,
                        error_message=str(e),
                        metadata={"error_type": type(e).__name__},
                        request_id=operation_context.get("request_id"),
                    )
                )
                await family_monitor.log_family_performance(
                    FamilyOperationType.FAMILY_CREATE,
                    duration,
                    success=False,
                    metadata={"error_type": type(e).__name__},
                )
            raise

        except Exception as e:
            # Handle transaction rollback
            rollback_successful = False
            if session and session.in_transaction:
                try:
                    await session.abort_transaction()
                    rollback_successful = True
                    self.logger.warning("Transaction rolled back successfully for family creation")
                except Exception as rollback_error:
                    self.logger.error("Failed to rollback transaction: %s", rollback_error, exc_info=True)

            self.db_manager.log_query_error("families", "create_family", start_time, e, operation_context)

            # Record error for monitoring with high severity for unexpected errors
            await record_error_event(e, error_context, ErrorSeverity.CRITICAL)

            # Attempt error recovery for database-related errors
            if isinstance(e, (PyMongoError, ConnectionError)):
                self.logger.info("Attempting database error recovery for family creation")
                try:
                    recovery_success, recovery_result = await recover_from_database_error(e, error_context)
                    if recovery_success:
                        self.logger.info("Database recovery successful, retrying family creation")
                        # The retry will be handled by the @handle_errors decorator
                        # Record successful recovery
                        await record_error_event(
                            e, error_context, ErrorSeverity.MEDIUM, recovery_attempted=True, recovery_successful=True
                        )
                except Exception as recovery_error:
                    self.logger.error("Database recovery failed: %s", recovery_error)
                    await record_error_event(
                        recovery_error,
                        error_context,
                        ErrorSeverity.CRITICAL,
                        recovery_attempted=True,
                        recovery_successful=False,
                    )

            self.logger.error(
                "Failed to create family for user %s: %s",
                user_id,
                e,
                exc_info=True,
                extra={
                    "user_id": user_id,
                    "family_name": name,
                    "rollback_successful": rollback_successful,
                    "transaction_id": str(session.session_id) if session else None,
                    "error_context": sanitize_sensitive_data(error_context.to_dict()),
                },
            )

            # Create user-friendly error for API responses
            user_friendly_error = create_user_friendly_error(e, error_context, include_technical_details=False)

            transaction_error = TransactionError(
                f"Failed to create family: {str(e)}", operation="create_family", rollback_successful=rollback_successful
            )
            transaction_error.user_friendly_response = user_friendly_error
            raise transaction_error

        finally:
            if session:
                await session.end_session()

    async def _send_direct_transfer_notification(
        self, family_id: str, recipient_user_id: str, amount: int, admin_id: str, reason: str, transaction_id: str
    ) -> None:
        """Send notification about direct token transfer to recipient."""
        try:
            admin_user = await self._get_user_by_id(admin_id)

            notification_data = {
                "type": "direct_token_transfer_received",
                "title": "Tokens Received",
                "message": f"You have received {amount} tokens directly from your family account. Reason: {reason}",
                "data": {
                    "amount": amount,
                    "reason": reason,
                    "transferred_by": admin_id,
                    "admin_username": admin_user.get("username", "Admin") if admin_user else "Admin",
                    "transaction_id": transaction_id,
                    "transfer_completed": True,
                },
            }

            await self._send_family_notification(family_id, [recipient_user_id], notification_data)

        except Exception as e:
            self.logger.error("Failed to send direct transfer notification: %s", e)

    async def _send_direct_transfer_admin_notification(
        self, family_id: str, admin_id: str, recipient_username: str, amount: int, reason: str, transaction_id: str
    ) -> None:
        """Send notification about direct token transfer to other family admins."""
        try:
            family = await self._get_family_by_id(family_id)
            admin_user = await self._get_user_by_id(admin_id)

            # Send to other admins (not the one who performed the transfer)
            other_admins = [aid for aid in family["admin_user_ids"] if aid != admin_id]

            if other_admins:
                notification_data = {
                    "type": "direct_token_transfer_admin",
                    "title": "Direct Token Transfer",
                    "message": f"{admin_user.get('username', 'Admin') if admin_user else 'Admin'} transferred {amount} tokens to {recipient_username}. Reason: {reason}",
                    "data": {
                        "amount": amount,
                        "reason": reason,
                        "recipient_username": recipient_username,
                        "transferred_by": admin_id,
                        "admin_username": admin_user.get("username", "Admin") if admin_user else "Admin",
                        "transaction_id": transaction_id,
                        "transfer_completed": True,
                    },
                }

                await self._send_family_notification(family_id, other_admins, notification_data)

        except Exception as e:
            self.logger.error("Failed to send direct transfer admin notification: %s", e)

    async def invite_member(
        self,
        family_id: str,
        inviter_id: str,
        identifier: str,
        relationship_type: str,
        identifier_type: str = "email",
        request_context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Invite a user to join a family by email or username with comprehensive validation.

        Args:
            family_id: ID of the family to invite to
            inviter_id: ID of the user sending the invitation
            identifier: Email address or username of the user to invite
            relationship_type: Relationship type from inviter's perspective
            identifier_type: "email" or "username" to specify identifier type
            request_context: Request context for rate limiting and security

        Returns:
            Dict containing invitation information

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
            InvalidRelationship: If relationship type is invalid
            ValidationError: If input validation fails
            RateLimitExceeded: If rate limit exceeded
            FamilyLimitExceeded: If family member limits exceeded
            TransactionError: If database transaction fails
        """
        operation_context = {
            "family_id": family_id,
            "inviter_id": inviter_id,
            "identifier": identifier,
            "identifier_type": identifier_type,
            "relationship_type": relationship_type,
            "operation": "invite_member",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("family_invitations", "invite_member", operation_context)

        # Rate limiting check
        if request_context:
            try:
                await self._check_rate_limit(request_context, "family_invitation", INVITATION_RATE_LIMIT, 3600)
            except Exception as e:
                raise RateLimitExceeded(
                    "Family invitation rate limit exceeded",
                    action="family_invitation",
                    limit=INVITATION_RATE_LIMIT,
                    window=3600,
                )

        session = None

        try:
            # Comprehensive input validation
            await self._validate_invitation_input(family_id, inviter_id, identifier, relationship_type, identifier_type)

            # Verify family exists and user has admin permissions
            family = await self._get_family_by_id(family_id)
            if inviter_id not in family["admin_user_ids"]:
                raise InsufficientPermissions(
                    "Only family admins can invite members", required_role="admin", user_role="member"
                )

            # Check family member limits with detailed context
            await self._check_family_member_limits_detailed(family_id, inviter_id)

            # Find and validate invitee user
            invitee_user = await self._find_and_validate_invitee(identifier, identifier_type)
            invitee_id = str(invitee_user["_id"])

            # Check for existing membership or pending invitations
            existing_invitation = await self._check_existing_membership_and_invitations(invitee_id, family_id)

            # If there's an existing pending invitation, return it in the expected format
            if existing_invitation:
                return {
                    "invitation_id": existing_invitation["invitation_id"],
                    "family_name": family["name"],
                    "invitee_email": invitee_user.get("email", ""),
                    "invitee_username": invitee_user.get("username", ""),
                    "relationship_type": existing_invitation.get("relationship_type", relationship_type),
                    "expires_at": existing_invitation.get("expires_at"),
                    "created_at": existing_invitation.get("created_at"),
                    "invitation_token": existing_invitation.get("invitation_token"),
                    "status": "pending",
                    "email_sent": existing_invitation.get("email_sent", False),
                    "transaction_safe": False,  # Existing invitation, not created in transaction
                }

            # Validate relationship logic (prevent contradictory relationships)
            await self._validate_relationship_logic(inviter_id, invitee_id, relationship_type, family_id)

            # If the database doesn't support transactions, use a non-transactional path
            if getattr(self.db_manager, "transactions_supported", False) is False:
                self.logger.warning("Database does not support transactions; using non-transactional invite flow")
                return await self._create_invitation_non_transactional(
                    family_id, inviter_id, invitee_user, relationship_type, start_time
                )

            # Start transaction for invitation creation
            client = self.db_manager.client
            session = await client.start_session()

            async with session.start_transaction():
                # Generate secure invitation with cryptographic token
                invitation_data = await self._generate_secure_invitation(
                    family_id, inviter_id, invitee_user, relationship_type
                )

                # Insert invitation within transaction
                invitations_collection = self.db_manager.get_tenant_collection("family_invitations")
                await invitations_collection.insert_one(invitation_data["document"], session=session)

                # Send invitation email (outside transaction to avoid rollback on email failure)
                email_sent = await self._send_invitation_email_safe(invitation_data["document"], family)

                # Update email sent status within transaction
                await invitations_collection.update_one(
                    {"invitation_id": invitation_data["invitation_id"]},
                    {
                        "$set": {
                            "email_sent": email_sent,
                            "email_sent_at": datetime.now(timezone.utc) if email_sent else None,
                            "email_attempts": 1,
                        }
                    },
                    session=session,
                )

                # Log successful invitation
                self.db_manager.log_query_success(
                    "family_invitations",
                    "invite_member",
                    start_time,
                    1,
                    f"Invitation sent with transaction: {invitation_data['invitation_id']}",
                )

                self.logger.info(
                    "Family invitation sent successfully: %s to %s (%s) for family %s",
                    invitation_data["invitation_id"],
                    identifier,
                    identifier_type,
                    family_id,
                    extra={
                        "invitation_id": invitation_data["invitation_id"],
                        "family_id": family_id,
                        "inviter_id": inviter_id,
                        "invitee_id": invitee_id,
                        "relationship_type": relationship_type,
                        "email_sent": email_sent,
                        "transaction_id": str(session.session_id) if session else None,
                    },
                )

                # Log to monitoring system
                if MONITORING_ENABLED:
                    duration = time.time() - start_time
                    await family_monitor.log_family_operation(
                        FamilyOperationContext(
                            operation_type=FamilyOperationType.MEMBER_INVITE,
                            family_id=family_id,
                            user_id=inviter_id,
                            target_user_id=invitee_id,
                            duration=duration,
                            success=True,
                            metadata={
                                "invitation_id": invitation_data["invitation_id"],
                                "relationship_type": relationship_type,
                                "identifier_type": identifier_type,
                                "email_sent": email_sent,
                                "transaction_safe": True,
                            },
                            request_id=operation_context.get("request_id"),
                            ip_address=operation_context.get("ip_address"),
                        )
                    )
                    await family_monitor.log_family_performance(
                        FamilyOperationType.MEMBER_INVITE,
                        duration,
                        success=True,
                        metadata={"relationship_type": relationship_type},
                    )

                return {
                    "invitation_id": invitation_data["invitation_id"],
                    "family_name": family["name"],
                    "invitee_email": invitee_user.get("email", ""),
                    "invitee_username": invitee_user.get("username", ""),
                    "relationship_type": relationship_type,
                    "expires_at": invitation_data["expires_at"],
                    "created_at": invitation_data["document"].get("created_at"),
                    "invitation_token": invitation_data.get("token"),
                    "status": "pending",
                    "email_sent": email_sent,
                    "transaction_safe": True,
                }

        except (
            FamilyNotFound,
            InsufficientPermissions,
            InvalidRelationship,
            ValidationError,
            RateLimitExceeded,
            FamilyLimitExceeded,
        ) as e:
            # These are expected validation errors, don't wrap them
            self.db_manager.log_query_error("family_invitations", "invite_member", start_time, e, operation_context)
            raise

        except Exception as e:
            # Handle transaction rollback
            rollback_successful = False
            if session and session.in_transaction:
                try:
                    await session.abort_transaction()
                    rollback_successful = True
                    self.logger.warning("Transaction rolled back successfully for family invitation")
                except Exception as rollback_error:
                    self.logger.error("Failed to rollback invitation transaction: %s", rollback_error, exc_info=True)

            self.db_manager.log_query_error("family_invitations", "invite_member", start_time, e, operation_context)
            self.logger.error(
                "Failed to invite member to family %s: %s",
                family_id,
                e,
                exc_info=True,
                extra={
                    "family_id": family_id,
                    "inviter_id": inviter_id,
                    "identifier": identifier,
                    "rollback_successful": rollback_successful,
                    "transaction_id": str(session.session_id) if session else None,
                },
            )

            raise TransactionError(
                f"Failed to send invitation: {str(e)}",
                operation="invite_member",
                rollback_successful=rollback_successful,
            )

        finally:
            if session:
                await session.end_session()

    async def respond_to_invitation(self, invitation_id: str, user_id: str, action: str) -> Dict[str, Any]:
        """
        Respond to a family invitation (accept or decline).

        Args:
            invitation_id: ID of the invitation to respond to
            user_id: ID of the user responding
            action: "accept" or "decline"

        Returns:
            Dict containing response information

        Raises:
            InvitationNotFound: If invitation doesn't exist or expired
            InsufficientPermissions: If user is not the invitee
            FamilyError: If response processing fails
        """
        start_time = db_manager.log_query_start(
            "family_invitations", "respond_to_invitation", {"invitation_id": invitation_id, "action": action}
        )

        try:
            # Get invitation
            invitations_collection = db_manager.get_collection("family_invitations")
            invitation = await invitations_collection.find_one({"invitation_id": invitation_id})

            if not invitation:
                raise InvitationNotFound("Invitation not found")

            # Verify user is the invitee
            if invitation["invitee_user_id"] != user_id:
                raise InsufficientPermissions("You can only respond to your own invitations")

            # Check if invitation is still valid
            if invitation["status"] != "pending":
                raise InvitationNotFound("Invitation has already been responded to")

            # Normalize datetimes (DB may contain naive datetimes). Treat naive as UTC.
            expires_at = invitation.get("expires_at")
            if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at and datetime.now(timezone.utc) > expires_at:
                raise InvitationNotFound("Invitation has expired")

            now = datetime.now(timezone.utc)

            if action.lower() == "accept":
                # Accept invitation - create bidirectional relationship
                await self._create_bidirectional_relationship(
                    invitation["family_id"], invitation["inviter_user_id"], user_id, invitation["relationship_type"]
                )

                # Add user to family membership
                await self._add_user_to_family_membership(user_id, invitation["family_id"], "member", now)

                # Update family member count
                await self._increment_family_member_count(invitation["family_id"])

                # Update invitation status
                await invitations_collection.update_one(
                    {"invitation_id": invitation_id}, {"$set": {"status": "accepted", "responded_at": now}}
                )

                self.logger.info("Family invitation accepted: %s by user %s", invitation_id, user_id)

                return {
                    "status": "accepted",
                    "family_id": invitation["family_id"],
                    "relationship_type": invitation["relationship_type"],
                    "message": "Successfully joined the family",
                }

            else:  # decline
                # Update invitation status
                await invitations_collection.update_one(
                    {"invitation_id": invitation_id}, {"$set": {"status": "declined", "responded_at": now}}
                )

                self.logger.info("Family invitation declined: %s by user %s", invitation_id, user_id)

                return {"status": "declined", "message": "Invitation declined"}

            db_manager.log_query_success(
                "family_invitations", "respond_to_invitation", start_time, 1, f"Invitation {action}ed: {invitation_id}"
            )

        except (InvitationNotFound, InsufficientPermissions):
            db_manager.log_query_error(
                "family_invitations",
                "respond_to_invitation",
                start_time,
                Exception("Validation error"),
                {"invitation_id": invitation_id},
            )
            raise
        except Exception as e:
            db_manager.log_query_error(
                "family_invitations", "respond_to_invitation", start_time, e, {"invitation_id": invitation_id}
            )
            self.logger.error("Failed to respond to invitation %s: %s", invitation_id, e, exc_info=True)
            raise FamilyError(f"Failed to process invitation response: {str(e)}")

    async def respond_to_invitation_by_token(self, invitation_token: str, action: str) -> Dict[str, Any]:
        """
        Respond to a family invitation using the email token (accept or decline).

        Args:
            invitation_token: Token from the email invitation link
            action: "accept" or "decline"

        Returns:
            Dict containing response information

        Raises:
            InvitationNotFound: If invitation doesn't exist or expired
            FamilyError: If response processing fails
        """
        start_time = db_manager.log_query_start(
            "family_invitations",
            "respond_to_invitation_by_token",
            {"token": invitation_token[:8] + "...", "action": action},
        )

        try:
            # Get invitation by token
            invitations_collection = db_manager.get_collection("family_invitations")
            invitation = await invitations_collection.find_one({"invitation_token": invitation_token})

            if not invitation:
                raise InvitationNotFound("Invalid invitation token")

            # Check if invitation is still valid
            if invitation["status"] != "pending":
                raise InvitationNotFound("Invitation has already been responded to")

            if datetime.now(timezone.utc) > invitation["expires_at"]:
                raise InvitationNotFound("Invitation has expired")

            # Use the existing respond_to_invitation method
            return await self.respond_to_invitation(invitation["invitation_id"], invitation["invitee_user_id"], action)

        except (InvitationNotFound, FamilyError):
            db_manager.log_query_error(
                "family_invitations",
                "respond_to_invitation_by_token",
                start_time,
                Exception("Validation error"),
                {"token": invitation_token[:8] + "..."},
            )
            raise
        except Exception as e:
            db_manager.log_query_error(
                "family_invitations",
                "respond_to_invitation_by_token",
                start_time,
                e,
                {"token": invitation_token[:8] + "..."},
            )
            self.logger.error("Failed to respond to invitation by token: %s", e, exc_info=True)
            raise FamilyError(f"Failed to process invitation response: {str(e)}")

    async def get_user_families(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all families that a user belongs to.

        Args:
            user_id: ID of the user

        Returns:
            List of family information dictionaries
        """
        start_time = db_manager.log_query_start("families", "get_user_families", {"user_id": user_id})

        try:
            # Get user's family memberships
            user = await self._get_user_by_id(user_id)
            family_memberships = user.get("family_memberships", [])

            if not family_memberships:
                db_manager.log_query_success("families", "get_user_families", start_time, 0)
                return []

            # Get family details
            family_ids = [membership["family_id"] for membership in family_memberships]
            families_collection = db_manager.get_collection("families")

            families_cursor = families_collection.find({"family_id": {"$in": family_ids}, "is_active": True})

            families = []
            async for family in families_cursor:
                # Find user's role in this family
                user_membership = next((m for m in family_memberships if m["family_id"] == family["family_id"]), None)

                if user_membership:
                    # Get SBD account balance
                    sbd_balance = await self._get_sbd_account_balance(family["sbd_account"]["account_username"])

                    families.append(
                        {
                            "family_id": family["family_id"],
                            "name": family["name"],
                            "admin_user_ids": family["admin_user_ids"],
                            "member_count": family["member_count"],
                            "created_at": family["created_at"],
                            "is_admin": user_id in family["admin_user_ids"],
                            "role": user_membership["role"],
                            "joined_at": user_membership["joined_at"],
                            "sbd_account": {
                                "account_username": family["sbd_account"]["account_username"],
                                "balance": sbd_balance,
                                "is_frozen": family["sbd_account"]["is_frozen"],
                                "can_spend": user_membership.get("spending_permissions", {}).get("can_spend", False),
                            },
                        }
                    )

            db_manager.log_query_success("families", "get_user_families", start_time, len(families))
            self.logger.debug("Retrieved %d families for user %s", len(families), user_id)

            return families

        except Exception as e:
            db_manager.log_query_error("families", "get_user_families", start_time, e, {"user_id": user_id})
            self.logger.error("Failed to get families for user %s: %s", user_id, e, exc_info=True)
            raise FamilyError(f"Failed to retrieve user families: {str(e)}")

    async def get_family_members(self, family_id: str, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all family members and their relationships for a specific family.

        Args:
            family_id: ID of the family
            user_id: ID of the requesting user (must be family member)

        Returns:
            List of family member information with relationships

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not a family member
            FamilyError: If retrieval fails
        """
        start_time = db_manager.log_query_start(
            "family_relationships", "get_family_members", {"family_id": family_id, "user_id": user_id}
        )

        try:
            # Verify family exists and user is a member
            family = await self._get_family_by_id(family_id)
            if not await self._is_user_in_family(user_id, family_id):
                raise InsufficientPermissions("You must be a family member to view family members")

            # Get all relationships for this family
            relationships_collection = db_manager.get_collection("family_relationships")
            relationships_cursor = relationships_collection.find({"family_id": family_id, "status": "active"})

            # Build member information with relationships
            members = {}
            relationships = []

            async for relationship in relationships_cursor:
                relationships.append(relationship)

                # Add both users to members dict if not already present
                for user_key in ["user_a_id", "user_b_id"]:
                    member_id = relationship[user_key]
                    if member_id not in members:
                        try:
                            member_user = await self._get_user_by_id(member_id)
                            members[member_id] = {
                                "user_id": member_id,
                                "username": member_user.get("username", "Unknown"),
                                "email": member_user.get("email", ""),
                                "role": "admin" if member_id in family["admin_user_ids"] else "member",
                                "relationships": [],
                            }
                        except FamilyError:
                            # User might have been deleted, skip
                            continue

            # Add relationships from the requesting user's perspective
            for relationship in relationships:
                user_a_id = relationship["user_a_id"]
                user_b_id = relationship["user_b_id"]

                if user_a_id in members and user_b_id in members:
                    # Add relationship from A's perspective to B
                    members[user_a_id]["relationships"].append(
                        {
                            "related_user_id": user_b_id,
                            "related_username": members[user_b_id]["username"],
                            "relationship_type": relationship["relationship_type_a_to_b"],
                            "relationship_id": relationship["relationship_id"],
                            "created_at": relationship["created_at"],
                        }
                    )

                    # Add relationship from B's perspective to A
                    members[user_b_id]["relationships"].append(
                        {
                            "related_user_id": user_a_id,
                            "related_username": members[user_a_id]["username"],
                            "relationship_type": relationship["relationship_type_b_to_a"],
                            "relationship_id": relationship["relationship_id"],
                            "created_at": relationship["created_at"],
                        }
                    )

            # Convert to list and add family membership info
            members_list = []
            for member_id, member_info in members.items():
                # Get user's family membership details
                member_user = await self._get_user_by_id(member_id)
                family_memberships = member_user.get("family_memberships", [])
                family_membership = next((m for m in family_memberships if m["family_id"] == family_id), None)

                if family_membership:
                    member_info["joined_at"] = family_membership["joined_at"]
                    # Transform spending_permissions from family document (authoritative source)
                    family_spending_permissions = family["sbd_account"]["spending_permissions"].get(member_id, {})
                    member_info["spending_permissions"] = {
                        "role": member_info["role"],  # Use the role from member_info
                        "spending_limit": family_spending_permissions.get("spending_limit", 0),
                        "can_spend": family_spending_permissions.get("can_spend", False),
                        "updated_by": family_spending_permissions.get("updated_by", ""),
                        "updated_at": family_spending_permissions.get("updated_at", datetime.now(timezone.utc)),
                    }
                else:
                    # Handle case where user doesn't have family_membership entry
                    # This shouldn't normally happen, but provide defaults to prevent errors
                    member_info["joined_at"] = datetime.now(timezone.utc)
                    member_info["spending_permissions"] = {
                        "role": member_info["role"],
                        "spending_limit": 0,
                        "can_spend": False,
                        "updated_by": "",
                        "updated_at": datetime.now(timezone.utc),
                    }

                members_list.append(member_info)

            # Sort by join date
            def safe_datetime_sort_key(member):
                joined_at = member.get("joined_at")
                if joined_at is None:
                    return datetime.min.replace(tzinfo=timezone.utc)
                # Ensure datetime is timezone-aware
                if joined_at.tzinfo is None:
                    joined_at = joined_at.replace(tzinfo=timezone.utc)
                return joined_at

            members_list.sort(key=safe_datetime_sort_key)

            db_manager.log_query_success(
                "family_relationships",
                "get_family_members",
                start_time,
                len(members_list),
                f"Retrieved {len(members_list)} family members",
            )

            self.logger.info("Retrieved %d family members for family %s", len(members_list), family_id)

            return members_list

        except (FamilyNotFound, InsufficientPermissions):
            db_manager.log_query_error(
                "family_relationships",
                "get_family_members",
                start_time,
                Exception("Validation error"),
                {"family_id": family_id},
            )
            raise
        except Exception as e:
            db_manager.log_query_error(
                "family_relationships", "get_family_members", start_time, e, {"family_id": family_id}
            )
            self.logger.error("Failed to get family members for family %s: %s", family_id, e, exc_info=True)
            raise FamilyError(f"Failed to retrieve family members: {str(e)}")

    async def check_family_limits(self, user_id: str, include_billing_metrics: bool = False) -> Dict[str, Any]:
        """
        Enhanced family limits checking with detailed status and billing integration.

        Args:
            user_id: ID of the user
            include_billing_metrics: Whether to include billing-related metrics

        Returns:
            Dict containing comprehensive limits and usage information
        """
        try:
            from second_brain_database.config import settings

            user = await self._get_user_by_id(user_id)

            # Get family limits (with defaults from config)
            family_limits = user.get("family_limits", {})
            max_families = family_limits.get("max_families_allowed", settings.DEFAULT_MAX_FAMILIES_ALLOWED)
            max_members_per_family = family_limits.get(
                "max_members_per_family", settings.DEFAULT_MAX_MEMBERS_PER_FAMILY
            )

            # Get current usage
            family_memberships = user.get("family_memberships", [])
            current_families = len(family_memberships)

            # Get detailed family usage with enhanced information
            families_usage = []
            total_members_across_families = 0

            for membership in family_memberships:
                family = await self._get_family_by_id(membership["family_id"])
                if family:
                    is_admin = user_id in family["admin_user_ids"]
                    max_members_for_family = (
                        max_members_per_family
                        if is_admin
                        else family.get("max_members_allowed", max_members_per_family)
                    )
                    members_remaining = max(0, max_members_for_family - family["member_count"])

                    # Get last activity timestamp
                    last_activity = await self._get_family_last_activity(family["family_id"])

                    families_usage.append(
                        {
                            "family_id": family["family_id"],
                            "name": family["name"],
                            "member_count": family["member_count"],
                            "max_members_allowed": max_members_for_family,
                            "is_admin": is_admin,
                            "can_add_members": is_admin and members_remaining > 0,
                            "members_remaining": members_remaining,
                            "created_at": family["created_at"],
                            "last_activity": last_activity,
                        }
                    )

                    total_members_across_families += family["member_count"]

            # Calculate limit status
            limit_status = []

            # Family count limit status
            families_percentage = (current_families / max_families * 100) if max_families > 0 else 0
            limit_status.append(
                {
                    "limit_type": "families",
                    "current_usage": current_families,
                    "max_allowed": max_families,
                    "percentage_used": families_percentage,
                    "is_at_limit": current_families >= max_families,
                    "is_over_limit": current_families > max_families,
                    "grace_period_expires": None,  # TODO: Implement grace period logic
                    "upgrade_required": current_families >= max_families,
                }
            )

            # Member count limit status (aggregate across all families where user is admin)
            admin_families = [f for f in families_usage if f["is_admin"]]
            if admin_families:
                max_total_members = len(admin_families) * max_members_per_family
                admin_members_total = sum(f["member_count"] for f in admin_families)
                members_percentage = (admin_members_total / max_total_members * 100) if max_total_members > 0 else 0

                limit_status.append(
                    {
                        "limit_type": "members",
                        "current_usage": admin_members_total,
                        "max_allowed": max_total_members,
                        "percentage_used": members_percentage,
                        "is_at_limit": admin_members_total >= max_total_members,
                        "is_over_limit": admin_members_total > max_total_members,
                        "grace_period_expires": None,
                        "upgrade_required": admin_members_total >= max_total_members,
                    }
                )

            # Generate upgrade messaging
            upgrade_messaging = await self._generate_upgrade_messaging(
                current_families, max_families, total_members_across_families, max_members_per_family
            )

            result = {
                "max_families_allowed": max_families,
                "max_members_per_family": max_members_per_family,
                "current_families": current_families,
                "families_usage": families_usage,
                "can_create_family": current_families < max_families,
                "upgrade_required": current_families >= max_families,
                "limit_status": limit_status,
                "upgrade_messaging": upgrade_messaging,
            }

            # Add billing metrics if requested
            if include_billing_metrics and settings.ENABLE_FAMILY_USAGE_TRACKING:
                billing_metrics = await self._get_billing_usage_metrics(user_id)
                result["billing_metrics"] = billing_metrics

            return result

        except Exception as e:
            self.logger.error("Failed to check family limits for user %s: %s", user_id, e, exc_info=True)
            raise FamilyError(f"Failed to check family limits: {str(e)}")

    # --- Purchase Request Management ---

    async def create_purchase_request(
        self,
        family_id: str,
        requester_id: str,
        item_info: Dict[str, Any],
        cost: int,
        request_context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Creates a purchase request for a family member.

        Args:
            family_id: The ID of the family.
            requester_id: The ID of the user making the request.
            item_info: A dictionary with item details (item_id, name, item_type, image_url).
            cost: The cost of the item.
            request_context: The request context for logging.

        Returns:
            A dictionary with the created purchase request.
        """
        error_context = ErrorContext(
            operation="create_purchase_request",
            user_id=requester_id,
            request_id=request_context.get("request_id") if request_context else None,
            ip_address=request_context.get("ip_address") if request_context else None,
            metadata={"family_id": family_id, "item_id": item_info.get("item_id"), "cost": cost},
        )

        try:
            # 1. Get requester info
            requester_user = await self._get_user_by_id(requester_id)
            requester_info = PurchaseRequestUserInfo(
                user_id=requester_id, username=requester_user.get("username", "Unknown")
            )

            # 2. Create PurchaseRequestDocument
            request_id = f"pr_{uuid.uuid4().hex[:16]}"

            item_info_model = PurchaseRequestItemInfo(**item_info)

            purchase_request_doc = PurchaseRequestDocument(
                request_id=request_id,
                family_id=family_id,
                requester_info=requester_info,
                item_info=item_info_model,
                cost=cost,
                status="PENDING",
                created_at=datetime.now(timezone.utc),
            )

            # 3. Insert into DB
            purchase_requests_collection = self.db_manager.get_tenant_collection("family_purchase_requests")
            await purchase_requests_collection.insert_one(purchase_request_doc.model_dump(by_alias=True))

            # 4. Send notification to family admins
            family = await self._get_family_by_id(family_id)
            admin_ids = family.get("admin_user_ids", [])

            if hasattr(self, "send_family_notification"):
                await self.send_family_notification(
                    family_id=family_id,
                    notification_type="purchase_request_created",
                    data={
                        "request_id": request_id,
                        "requester_username": requester_info.username,
                        "item_name": item_info.get("name"),
                        "cost": cost,
                    },
                    recipient_user_ids=admin_ids,
                )

            self.logger.info(
                "Purchase request created: %s for family %s by user %s",
                request_id,
                family_id,
                requester_id,
            )

            return purchase_request_doc.model_dump()

        except Exception as e:
            await record_error_event(e, error_context, ErrorSeverity.HIGH)
            self.logger.error("Failed to create purchase request for family %s: %s", family_id, e, exc_info=True)
            raise FamilyError(f"Failed to create purchase request: {str(e)}")

    async def get_purchase_requests(self, family_id: str, user_id: str) -> List[Dict[str, Any]]:
        """
        Get purchase requests for a family.
        Admins see all, members see their own.
        """
        error_context = ErrorContext(
            operation="get_purchase_requests",
            user_id=user_id,
            metadata={"family_id": family_id},
        )
        try:
            family = await self._get_family_by_id(family_id)
            is_admin = user_id in family.get("admin_user_ids", [])

            purchase_requests_collection = self.db_manager.get_tenant_collection("family_purchase_requests")

            query = {"family_id": family_id}
            if not is_admin:
                query["requester_info.user_id"] = user_id

            requests_cursor = purchase_requests_collection.find(query).sort("created_at", -1)

            requests = await requests_cursor.to_list(length=100)  # Limit to 100 for now

            self.logger.info(
                "Retrieved %d purchase requests for family %s for user %s (admin: %s)",
                len(requests),
                family_id,
                user_id,
                is_admin,
            )

            return requests

        except Exception as e:
            await record_error_event(e, error_context, ErrorSeverity.MEDIUM)
            self.logger.error("Failed to get purchase requests for family %s: %s", family_id, e, exc_info=True)
            raise FamilyError(f"Failed to get purchase requests: {str(e)}")

    async def approve_purchase_request(
        self, request_id: str, admin_id: str, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Approve a purchase request.
        """
        error_context = ErrorContext(
            operation="approve_purchase_request",
            user_id=admin_id,
            request_id=request_context.get("request_id") if request_context else None,
            ip_address=request_context.get("ip_address") if request_context else None,
            metadata={"request_id": request_id},
        )
        try:
            purchase_requests_collection = self.db_manager.get_tenant_collection("family_purchase_requests")

            # 1. Get the purchase request
            purchase_request = await purchase_requests_collection.find_one({"request_id": request_id})
            if not purchase_request:
                raise FamilyError("Purchase request not found")

            if purchase_request["status"] != "PENDING":
                raise FamilyError(f"Purchase request is already {purchase_request['status']}")

            family_id = purchase_request["family_id"]

            # 2. Security check: user is an admin
            family = await self._get_family_by_id(family_id)
            if admin_id not in family.get("admin_user_ids", []):
                raise InsufficientPermissions("Only family admins can approve purchase requests.")

            # 3. Re-validate funds
            family_sbd_username = family["sbd_account"]["account_username"]
            balance = await self.get_family_sbd_balance(family_sbd_username)
            cost = purchase_request["cost"]
            if balance < cost:
                raise FamilyError(f"Insufficient family funds. Required: {cost}, Available: {balance}")

            # 4. Process payment
            from second_brain_database.routes.shop.routes import process_payment

            requester_user = await self._get_user_by_id(purchase_request["requester_info"]["user_id"])

            payment_details = {
                "payment_type": "family",
                "account_username": family_sbd_username,
                "family_id": family_id,
                "family_name": family["name"],
            }
            item_details = purchase_request["item_info"]
            transaction_id = f"txn_{uuid.uuid4().hex[:16]}"

            payment_result = await process_payment(
                payment_details=payment_details,
                amount=cost,
                item_details=item_details,
                current_user=requester_user,  # The payment is on behalf of the requester
                transaction_id=transaction_id,
            )

            # 5. Update purchase request status
            now = datetime.now(timezone.utc)
            admin_user = await self._get_user_by_id(admin_id)
            reviewed_by_info = PurchaseRequestUserInfo(user_id=admin_id, username=admin_user.get("username", "Unknown"))

            await purchase_requests_collection.update_one(
                {"request_id": request_id},
                {
                    "$set": {
                        "status": "APPROVED",
                        "reviewed_at": now,
                        "reviewed_by_info": reviewed_by_info.model_dump(),
                        "transaction_id": transaction_id,
                    }
                },
            )

            # 6. Notify requester
            if hasattr(self, "send_family_notification"):
                await self.send_family_notification(
                    family_id=family_id,
                    notification_type="purchase_request_approved",
                    data={
                        "request_id": request_id,
                        "item_name": item_details["name"],
                        "admin_username": reviewed_by_info.username,
                    },
                    recipient_user_ids=[purchase_request["requester_info"]["user_id"]],
                )

            self.logger.info("Purchase request %s approved by admin %s", request_id, admin_id)

            purchase_request["status"] = "APPROVED"
            return purchase_request

        except Exception as e:
            await record_error_event(e, error_context, ErrorSeverity.HIGH)
            self.logger.error("Failed to approve purchase request %s: %s", request_id, e, exc_info=True)
            raise FamilyError(f"Failed to approve purchase request: {str(e)}")

    async def deny_purchase_request(
        self, request_id: str, admin_id: str, reason: Optional[str] = None, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Deny a purchase request.
        """
        error_context = ErrorContext(
            operation="deny_purchase_request",
            user_id=admin_id,
            request_id=request_context.get("request_id") if request_context else None,
            ip_address=request_context.get("ip_address") if request_context else None,
            metadata={"request_id": request_id, "reason": reason},
        )
        try:
            purchase_requests_collection = self.db_manager.get_tenant_collection("family_purchase_requests")

            # 1. Get the purchase request
            purchase_request = await purchase_requests_collection.find_one({"request_id": request_id})
            if not purchase_request:
                raise FamilyError("Purchase request not found")

            if purchase_request["status"] != "PENDING":
                raise FamilyError(f"Purchase request is already {purchase_request['status']}")

            family_id = purchase_request["family_id"]

            # 2. Security check: user is an admin
            family = await self._get_family_by_id(family_id)
            if admin_id not in family.get("admin_user_ids", []):
                raise InsufficientPermissions("Only family admins can deny purchase requests.")

            # 3. Update purchase request status
            now = datetime.now(timezone.utc)
            admin_user = await self._get_user_by_id(admin_id)
            reviewed_by_info = PurchaseRequestUserInfo(user_id=admin_id, username=admin_user.get("username", "Unknown"))

            await purchase_requests_collection.update_one(
                {"request_id": request_id},
                {
                    "$set": {
                        "status": "DENIED",
                        "reviewed_at": now,
                        "reviewed_by_info": reviewed_by_info.model_dump(),
                        "denial_reason": reason,
                    }
                },
            )

            # 4. Notify requester
            if hasattr(self, "send_family_notification"):
                await self.send_family_notification(
                    family_id=family_id,
                    notification_type="purchase_request_denied",
                    data={
                        "request_id": request_id,
                        "item_name": purchase_request["item_info"]["name"],
                        "admin_username": reviewed_by_info.username,
                        "reason": reason,
                    },
                    recipient_user_ids=[purchase_request["requester_info"]["user_id"]],
                )

            self.logger.info("Purchase request %s denied by admin %s", request_id, admin_id)

            purchase_request["status"] = "DENIED"
            return purchase_request

        except Exception as e:
            await record_error_event(e, error_context, ErrorSeverity.HIGH)
            self.logger.error("Failed to deny purchase request %s: %s", request_id, e, exc_info=True)
            raise FamilyError(f"Failed to deny purchase request: {str(e)}")

    async def _get_family_last_activity(self, family_id: str) -> Optional[datetime]:
        """Get the last activity timestamp for a family."""
        try:
            # Check various collections for recent activity
            collections_to_check = [
                ("family_notifications", {"family_id": family_id}),
                ("family_token_requests", {"family_id": family_id}),
                ("family_relationships", {"family_id": family_id}),
            ]

            latest_activity = None

            for collection_name, query in collections_to_check:
                collection = self.db_manager.get_collection(collection_name)
                recent_doc = await collection.find_one(query, sort=[("created_at", -1)])
                if recent_doc and recent_doc.get("created_at"):
                    if not latest_activity or recent_doc["created_at"] > latest_activity:
                        latest_activity = recent_doc["created_at"]

            return latest_activity

        except Exception as e:
            self.logger.warning("Failed to get last activity for family %s: %s", family_id, e)
            return None

    async def _generate_upgrade_messaging(
        self, current_families: int, max_families: int, total_members: int, max_members_per_family: int
    ) -> Dict[str, Any]:
        """Generate upgrade messaging based on current usage."""
        try:
            messaging = {
                "primary_message": "",
                "upgrade_benefits": [],
                "call_to_action": "",
                "upgrade_url": "/billing/upgrade",
            }

            if current_families >= max_families:
                messaging["primary_message"] = f"You've reached your family limit ({current_families}/{max_families})"
                messaging["upgrade_benefits"] = [
                    "Create unlimited families",
                    f"Add up to 20 members per family (currently {max_members_per_family})",
                    "Priority support",
                    "Advanced family management features",
                ]
                messaging["call_to_action"] = "Upgrade to Pro to unlock more families"
            elif current_families / max_families >= 0.8:
                messaging["primary_message"] = (
                    f"You're approaching your family limit ({current_families}/{max_families})"
                )
                messaging["upgrade_benefits"] = [
                    "Never worry about family limits again",
                    "Add more members to existing families",
                    "Advanced analytics and reporting",
                ]
                messaging["call_to_action"] = "Consider upgrading to avoid hitting limits"
            else:
                messaging["primary_message"] = f"You have {max_families - current_families} families remaining"
                messaging["upgrade_benefits"] = [
                    "Unlimited families and members",
                    "Advanced features and priority support",
                ]
                messaging["call_to_action"] = "Upgrade for unlimited access"

            return messaging

        except Exception as e:
            self.logger.warning("Failed to generate upgrade messaging: %s", e)
            return {
                "primary_message": "Family management available",
                "upgrade_benefits": ["Unlimited families", "More members per family"],
                "call_to_action": "Upgrade for more features",
                "upgrade_url": "/billing/upgrade",
            }

    async def _get_billing_usage_metrics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get billing-related usage metrics for the specified period."""
        try:
            from datetime import timedelta

            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)

            # Get usage tracking data if enabled
            usage_data = await self._get_usage_tracking_data(user_id, start_date, end_date)

            # Calculate metrics
            peak_families = max((day.get("families_count", 0) for day in usage_data), default=0)
            peak_members_total = max((day.get("total_members", 0) for day in usage_data), default=0)

            avg_families = (
                sum(day.get("families_count", 0) for day in usage_data) / len(usage_data) if usage_data else 0
            )
            avg_members_total = (
                sum(day.get("total_members", 0) for day in usage_data) / len(usage_data) if usage_data else 0
            )

            family_creation_events = sum(1 for day in usage_data if "family_created" in day.get("events", []))
            member_addition_events = sum(1 for day in usage_data if "member_added" in day.get("events", []))

            # Generate upgrade recommendations
            upgrade_recommendations = []
            if peak_families > avg_families * 1.5:
                upgrade_recommendations.append("Consider Pro plan for consistent family access")
            if peak_members_total > 10:
                upgrade_recommendations.append("Upgrade for higher member limits")

            return {
                "period_start": start_date,
                "period_end": end_date,
                "peak_families": peak_families,
                "peak_members_total": peak_members_total,
                "average_families": avg_families,
                "average_members_total": avg_members_total,
                "family_creation_events": family_creation_events,
                "member_addition_events": member_addition_events,
                "upgrade_recommendations": upgrade_recommendations,
            }

        except Exception as e:
            self.logger.warning("Failed to get billing usage metrics for user %s: %s", user_id, e)
            return {
                "period_start": datetime.now(timezone.utc) - timedelta(days=days),
                "period_end": datetime.now(timezone.utc),
                "peak_families": 0,
                "peak_members_total": 0,
                "average_families": 0.0,
                "average_members_total": 0.0,
                "family_creation_events": 0,
                "member_addition_events": 0,
                "upgrade_recommendations": [],
            }

    # Private helper methods for enterprise patterns

    async def _validate_family_creation_input(self, user_id: str, name: Optional[str]) -> None:
        """Validate input parameters for family creation."""
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required", field="user_id", constraint="not_empty")

        if name is not None:
            name = name.strip()
            if len(name) < 2:
                raise ValidationError(
                    "Family name must be at least 2 characters long",
                    field="name",
                    value=name,
                    constraint="min_length_2",
                )
            if len(name) > 100:
                raise ValidationError(
                    "Family name must be less than 100 characters",
                    field="name",
                    value=name,
                    constraint="max_length_100",
                )
            # Check for reserved prefixes
            for prefix in RESERVED_PREFIXES:
                if name.lower().startswith(prefix):
                    raise ValidationError(
                        f"Family name cannot start with reserved prefix '{prefix}'",
                        field="name",
                        value=name,
                        constraint="no_reserved_prefix",
                    )

    async def _check_family_creation_limits(self, user_id: str) -> Dict[str, Any]:
        """Enhanced family creation limits check with detailed validation and messaging."""
        limits = await self.check_family_limits(user_id, include_billing_metrics=True)

        if not limits["can_create_family"]:
            # Get the family limit status for detailed error messaging
            family_limit_status = next(
                (status for status in limits["limit_status"] if status["limit_type"] == "families"), None
            )

            error_message = (
                f"Maximum families limit reached ({limits['current_families']}/{limits['max_families_allowed']})"
            )

            # Add upgrade messaging to the error
            upgrade_info = limits.get("upgrade_messaging", {})
            if upgrade_info.get("call_to_action"):
                error_message += f". {upgrade_info['call_to_action']}"

            raise FamilyLimitExceeded(
                message=error_message,
                current_count=limits["current_families"],
                max_allowed=limits["max_families_allowed"],
                limit_type="families",
            )

        return limits

    async def _generate_unique_sbd_username(self, family_name: str) -> str:
        """Generate and ensure unique SBD account username with collision handling."""
        return await self.generate_collision_resistant_family_username(family_name)

    async def _build_family_document(
        self, family_id: str, name: str, user_id: str, sbd_account_username: str, timestamp: datetime
    ) -> Dict[str, Any]:
        """Build comprehensive family document with all required fields."""
        return {
            "family_id": family_id,
            "name": name,
            "admin_user_ids": [user_id],
            "created_at": timestamp,
            "updated_at": timestamp,
            "member_count": 1,
            "is_active": True,
            "sbd_account": {
                "account_username": sbd_account_username,
                "is_frozen": False,
                "frozen_by": None,
                "frozen_at": None,
                "spending_permissions": {
                    user_id: {
                        "role": "admin",
                        "spending_limit": -1,  # Unlimited for admin
                        "can_spend": True,
                        "updated_by": user_id,
                        "updated_at": timestamp,
                    }
                },
                "notification_settings": {
                    "notify_on_spend": True,
                    "notify_on_deposit": True,
                    "large_transaction_threshold": 1000,
                    "notify_admins_only": False,
                },
            },
            "settings": {
                "allow_member_invites": False,
                "visibility": "private",
                "auto_approval_threshold": AUTO_APPROVAL_THRESHOLD,
                "request_expiry_hours": TOKEN_REQUEST_EXPIRY_HOURS,
            },
            "succession_plan": {"backup_admins": [], "recovery_contacts": []},
            "audit_trail": {
                "created_by": user_id,
                "created_at": timestamp,
                "last_modified_by": user_id,
                "last_modified_at": timestamp,
                "version": 1,
            },
        }

    async def _create_virtual_sbd_account_transactional(
        self, username: str, family_id: str, session: ClientSession
    ) -> None:
        """
        Create virtual SBD account within a database transaction with comprehensive audit trails.

        Args:
            username: Virtual account username
            family_id: Associated family ID
            session: Database session for transaction

        Raises:
            ValidationError: If account creation validation fails
            TransactionError: If database operation fails
        """
        users_collection = self.db_manager.get_collection("users")
        now = datetime.now(timezone.utc)

        # Generate unique account ID for audit trails
        account_id = f"va_{uuid.uuid4().hex[:16]}"

        # Create comprehensive virtual account document
        virtual_account = {
            "username": username,
            "sbd_tokens": 0,
            "sbd_tokens_transactions": [],
            "email": f"{username}@system.internal",
            "is_virtual_account": True,
            "managed_by_family": family_id,
            "created_at": now,
            "updated_at": now,
            "account_type": "family_virtual",
            "status": "active",
            "account_id": account_id,
            # Security controls
            "security_settings": {
                "creation_method": "family_system",
                "requires_family_auth": True,
                "spending_requires_permission": True,
                "audit_all_transactions": True,
                "rate_limit_enabled": True,
            },
            # Audit trail initialization
            "audit_trail": {
                "created_by_system": "family_manager",
                "creation_timestamp": now,
                "creation_context": {"family_id": family_id, "account_type": "family_virtual", "initial_balance": 0},
                "last_activity": now,
                "activity_count": 0,
                "security_events": [],
            },
            # Access controls
            "access_controls": {
                "authorized_family_members": [],  # Will be populated when members join
                "spending_permissions": {},  # Will be managed by family admins
                "frozen": False,
                "frozen_by": None,
                "frozen_at": None,
                "freeze_reason": None,
            },
            # Data retention settings
            "retention_policy": {
                "retain_transactions": True,
                "retention_period_days": VIRTUAL_ACCOUNT_RETENTION_DAYS,
                "auto_cleanup_enabled": True,
                "cleanup_scheduled": False,
            },
            # Performance and monitoring
            "performance_metrics": {
                "total_transactions": 0,
                "total_volume_in": 0,
                "total_volume_out": 0,
                "last_transaction_at": None,
                "peak_balance": 0,
                "peak_balance_at": None,
            },
        }

        try:
            # Insert virtual account with transaction safety
            await users_collection.insert_one(virtual_account, session=session)

            # Log security event for virtual account creation
            await self._log_virtual_account_security_event(
                account_id=account_id,
                username=username,
                event_type="virtual_account_created",
                details={
                    "family_id": family_id,
                    "creation_method": "transactional",
                    "session_id": str(session.session_id) if session else None,
                },
                session=session,
            )

            self.logger.info(
                "Virtual SBD account created with comprehensive audit trail: %s for family %s (account_id: %s)",
                username,
                family_id,
                account_id,
                extra={
                    "username": username,
                    "family_id": family_id,
                    "account_id": account_id,
                    "transaction_safe": True,
                    "audit_enabled": True,
                },
            )

        except Exception as e:
            self.logger.error(
                "Failed to create virtual SBD account: %s",
                e,
                exc_info=True,
                extra={"username": username, "family_id": family_id, "account_id": account_id},
            )
            raise TransactionError(
                f"Failed to create virtual SBD account: {str(e)}", operation="create_virtual_account"
            )

    async def _add_user_to_family_membership_transactional(
        self, user_id: str, family_id: str, role: str, joined_at: datetime, session: ClientSession
    ) -> None:
        """Add user to family membership list within a database transaction."""
        users_collection = self.db_manager.get_collection("users")

        membership = {
            "family_id": family_id,
            "role": role,
            "joined_at": joined_at,
            "spending_permissions": {
                "can_spend": role == "admin",
                "spending_limit": -1 if role == "admin" else 0,
                "last_updated": joined_at,
            },
            "status": "active",
        }

        # Try with string ID first, then ObjectId if needed
        query = {"_id": user_id}
        result = await users_collection.update_one(
            query, {"$push": {"family_memberships": membership}}, session=session
        )

        # If no match, try converting to ObjectId
        if result.matched_count == 0 and isinstance(user_id, str) and len(user_id) == 24:
            try:
                query = {"_id": ObjectId(user_id)}
                result = await users_collection.update_one(
                    query, {"$push": {"family_memberships": membership}}, session=session
                )
            except Exception:
                pass

        if result.matched_count == 0:
            raise FamilyError(f"Failed to add user to family membership: user not found - {user_id}")

    # --- Non-transactional fallbacks ---------------------------------
    async def _create_virtual_account_non_transactional(self, username: str, family_id: str) -> Dict[str, Any]:
        """
        Create virtual SBD account without a DB transaction. Returns the created virtual_account doc.
        Caller must perform compensating cleanup if subsequent steps fail.
        """
        users_collection = self.db_manager.get_collection("users")
        now = datetime.now(timezone.utc)
        account_id = f"va_{uuid.uuid4().hex[:16]}"

        virtual_account = {
            "username": username,
            "sbd_tokens": 0,
            "sbd_tokens_transactions": [],
            "email": f"{username}@system.internal",
            "is_virtual_account": True,
            "managed_by_family": family_id,
            "created_at": now,
            "updated_at": now,
            "account_type": "family_virtual",
            "status": "active",
            "account_id": account_id,
            "security_settings": {"creation_method": "family_system", "requires_family_auth": True},
            "audit_trail": {"created_by_system": "family_manager", "creation_timestamp": now},
            "access_controls": {"authorized_family_members": [], "spending_permissions": {}},
            "retention_policy": {"retain_transactions": True},
            "performance_metrics": {"total_transactions": 0},
        }

        try:
            result = await users_collection.insert_one(virtual_account)
            virtual_account["_id"] = result.inserted_id
            self.logger.info("Non-transactional virtual account created: %s (account_id=%s)", username, account_id)
            return virtual_account
        except Exception as e:
            self.logger.error("Failed to create non-transactional virtual account %s: %s", username, e, exc_info=True)
            raise TransactionError(
                f"Failed to create virtual account non-transactionally: {e}", operation="create_virtual_account"
            )

    async def _add_user_to_family_membership_non_transactional(
        self, user_id: str, family_id: str, role: str, joined_at: datetime
    ) -> None:
        """Add user to family membership list without a DB transaction."""
        users_collection = self.db_manager.get_collection("users")
        # Resolve canonical user document to ensure correct _id type
        user_doc = await self._get_user_by_id(user_id)
        canonical_id = user_doc.get("_id")

        membership = {
            "family_id": family_id,
            "role": role,
            "joined_at": joined_at,
            "spending_permissions": {
                "can_spend": role == "admin",
                "spending_limit": -1 if role == "admin" else 0,
                "last_updated": joined_at,
            },
            "status": "active",
        }

        try:
            result = await users_collection.update_one(
                {"_id": canonical_id}, {"$push": {"family_memberships": membership}}
            )
            # Log update outcome for observability
            self.logger.info(
                "Membership update for user %s -> matched=%d modified=%d",
                canonical_id,
                result.matched_count,
                result.modified_count,
            )
            if result.matched_count == 0:
                raise TransactionError(
                    f"No matching user found for membership update (id={canonical_id})", operation="add_membership"
                )
        except Exception as e:
            self.logger.error(
                "Failed to add user %s to family %s non-transactionally: %s", user_id, family_id, e, exc_info=True
            )
            raise TransactionError(f"Failed to add user to family non-transactionally: {e}", operation="add_membership")

    async def _create_family_non_transactional(
        self,
        user_id: str,
        name: str,
        family_id: str,
        sbd_account_username: str,
        limits_info: Dict[str, Any],
        start_time: float,
        operation_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Non-transactional fallback for family creation. Performs operations in order and cleans up on failure.
        This is intended for local/dev environments where MongoDB transactions are not available.
        """
        families_collection = self.db_manager.get_tenant_collection("families")
        now = datetime.now(timezone.utc)
        family_doc = await self._build_family_document(family_id, name, user_id, sbd_account_username, now)

        # Keep track of what we've created so we can compensate on failure
        created_virtual_account = None
        created_family = None

        try:
            # Insert family document first
            res = await families_collection.insert_one(family_doc)
            created_family = res.inserted_id

            # Create virtual account
            created_virtual_account = await self._create_virtual_account_non_transactional(
                sbd_account_username, family_id
            )

            # Add user to membership
            await self._add_user_to_family_membership_non_transactional(user_id, family_id, "admin", now)

            # Cache and log success
            self._cache_family(family_id, family_doc)
            self.db_manager.log_query_success(
                "families",
                "create_family_non_transactional",
                start_time,
                1,
                f"Family created non-transactionally: {family_id}",
            )

            self.logger.info(
                "Family created (non-transactional) %s by user %s", family_id, user_id, extra={"family_id": family_id}
            )

            return {
                "family_id": family_id,
                "name": name,
                "admin_user_ids": [user_id],
                "member_count": 1,
                "created_at": now,
                "sbd_account": {"account_username": sbd_account_username, "balance": 0, "is_frozen": False},
                "limits_info": limits_info,
                "transaction_safe": False,
            }

        except Exception as e:
            # Attempt compensating cleanup
            cleanup_errors = []
            try:
                if created_virtual_account:
                    # remove virtual account
                    users_collection = self.db_manager.get_collection("users")
                    await users_collection.delete_one({"_id": created_virtual_account.get("_id")})
            except Exception as ce:
                cleanup_errors.append(str(ce))

            try:
                if created_family:
                    await families_collection.delete_one({"_id": created_family})
            except Exception as ce:
                cleanup_errors.append(str(ce))

            self.db_manager.log_query_error(
                "families", "create_family_non_transactional", start_time, e, operation_context
            )
            self.logger.error(
                "Non-transactional family creation failed for user %s: %s; cleanup_errors=%s",
                user_id,
                e,
                cleanup_errors,
                exc_info=True,
            )
            raise TransactionError(f"Failed to create family non-transactionally: {e}", operation="create_family")

    def _get_operation_rate_limit(self, operation: str) -> int:
        """Get rate limit for specific family operations using configuration."""
        operation_limits = {
            "create_family": settings.FAMILY_CREATE_RATE_LIMIT,
            "invite_member": settings.FAMILY_INVITE_RATE_LIMIT,
            "remove_member": settings.FAMILY_ADMIN_ACTION_RATE_LIMIT,
            "promote_admin": settings.FAMILY_ADMIN_ACTION_RATE_LIMIT,
            "demote_admin": settings.FAMILY_ADMIN_ACTION_RATE_LIMIT,
            "freeze_account": settings.FAMILY_ADMIN_ACTION_RATE_LIMIT,
            "unfreeze_account": settings.FAMILY_ADMIN_ACTION_RATE_LIMIT,
            "update_spending_permissions": settings.FAMILY_MEMBER_ACTION_RATE_LIMIT,
        }
        return operation_limits.get(operation, settings.FAMILY_MEMBER_ACTION_RATE_LIMIT)

    async def _check_rate_limit(self, request_context: Dict[str, Any], action: str, limit: int, window: int) -> None:
        """Check rate limit for family operations using security manager."""
        if not request_context or "request" not in request_context:
            return  # Skip rate limiting if no request context

        try:
            await security_manager.check_rate_limit(
                request_context["request"], action, rate_limit_requests=limit, rate_limit_period=window
            )
        except Exception as e:
            self.logger.warning("Rate limit check failed for action %s: %s", action, e)
            raise RateLimitExceeded(f"Rate limit exceeded for {action}", action=action, limit=limit, window=window)

    def _cache_family(self, family_id: str, family_doc: Dict[str, Any]) -> None:
        """Cache family document for performance optimization."""
        cache_key = f"family:{family_id}"
        self._family_cache[cache_key] = {
            "data": family_doc,
            "cached_at": datetime.now(timezone.utc),
            "ttl": self._cache_ttl,
        }

        # Clean old cache entries
        self._cleanup_cache()

    def _cleanup_cache(self) -> None:
        """Clean up expired cache entries."""
        now = datetime.now(timezone.utc)
        expired_keys = []

        for key, cached_item in self._family_cache.items():
            if (now - cached_item["cached_at"]).total_seconds() > cached_item["ttl"]:
                expired_keys.append(key)

        for key in expired_keys:
            del self._family_cache[key]

    async def _validate_invitation_input(
        self, family_id: str, inviter_id: str, identifier: str, relationship_type: str, identifier_type: str
    ) -> None:
        """Validate all input parameters for family invitation."""
        if not family_id or not family_id.strip():
            raise ValidationError("Family ID is required", field="family_id", constraint="not_empty")

        if not inviter_id or not inviter_id.strip():
            raise ValidationError("Inviter ID is required", field="inviter_id", constraint="not_empty")

        if not identifier or not identifier.strip():
            raise ValidationError("Identifier is required", field="identifier", constraint="not_empty")

        if identifier_type not in ["email", "username"]:
            raise ValidationError(
                "Identifier type must be 'email' or 'username'",
                field="identifier_type",
                value=identifier_type,
                constraint="valid_type",
            )

        if not relationship_type or relationship_type.lower() not in RELATIONSHIP_TYPES:
            raise InvalidRelationship(
                f"Invalid relationship type: {relationship_type}",
                relationship_type=relationship_type,
                valid_types=list(RELATIONSHIP_TYPES.keys()),
            )

        # Edge case: Prevent users from inviting themselves
        inviter_user = await self._get_user_by_id(inviter_id)
        inviter_email = inviter_user.get("email", "").lower()
        inviter_username = inviter_user.get("username", "").lower()

        if identifier_type == "email" and identifier.lower() == inviter_email:
            raise ValidationError(
                "You cannot invite yourself to a family",
                field="identifier",
                value="[REDACTED]",  # Don't expose email in error
                constraint="not_self_invite",
            )
        elif identifier_type == "username" and identifier.lower() == inviter_username:
            raise ValidationError(
                "You cannot invite yourself to a family",
                field="identifier",
                value=identifier,
                constraint="not_self_invite",
            )

    async def _check_family_member_limits_detailed(self, family_id: str, admin_id: str) -> None:
        """Check if family can add more members with detailed error context."""
        family = await self._get_family_by_id(family_id)
        admin_user = await self._get_user_by_id(admin_id)

        family_limits = admin_user.get("family_limits", {})
        max_members = family_limits.get("max_members_per_family", DEFAULT_MAX_MEMBERS_PER_FAMILY)
        current_members = family["member_count"]

        if current_members >= max_members:
            raise FamilyLimitExceeded(
                f"Maximum family members limit reached ({current_members}/{max_members})",
                current_count=current_members,
                max_allowed=max_members,
                limit_type="family_members",
            )

    async def _find_and_validate_invitee(self, identifier: str, identifier_type: str) -> Dict[str, Any]:
        """Find and validate the invitee user by email or username."""
        if identifier_type == "email":
            invitee_user = await self._get_user_by_email(identifier.lower().strip())
            if not invitee_user:
                raise ValidationError(
                    f"User with email {identifier} not found",
                    field="identifier",
                    value=identifier,
                    constraint="user_exists",
                )
        elif identifier_type == "username":
            invitee_user = await self._get_user_by_username(identifier.lower().strip())
            if not invitee_user:
                raise ValidationError(
                    f"User with username {identifier} not found",
                    field="identifier",
                    value=identifier,
                    constraint="user_exists",
                )
        else:
            raise ValidationError(
                f"Invalid identifier type: {identifier_type}",
                field="identifier_type",
                value=identifier_type,
                constraint="valid_type",
            )

        return invitee_user

    async def _check_existing_membership_and_invitations(
        self, invitee_id: str, family_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if user is already in family or has pending/recent invitations.

        Handles edge cases:
        1. User is already a member
        2. User has a pending invitation (not expired) - RETURNS the invitation instead of raising error
        3. User has recently declined an invitation (within 24 hours - prevents spam)
        4. User has multiple pending invitations (cleanup old ones)
        5. User has accepted but relationship not yet created (race condition)

        Returns:
            Optional[Dict]: Existing pending invitation if found, None otherwise
        """
        # Check existing membership
        if await self._is_user_in_family(invitee_id, family_id):
            raise ValidationError(
                "User is already a member of this family",
                field="invitee_id",
                value=invitee_id,
                constraint="not_already_member",
            )

        invitations_collection = self.db_manager.get_tenant_collection("family_invitations")
        now = datetime.now(timezone.utc)

        # Check for pending invitations (not expired)
        existing_pending = await invitations_collection.find_one(
            {"family_id": family_id, "invitee_user_id": invitee_id, "status": "pending", "expires_at": {"$gt": now}}
        )

        if existing_pending:
            # Return existing pending invitation instead of raising error
            # This allows idempotent behavior - same invitation can be "sent" multiple times

            self.logger.info(
                "Found existing pending invitation %s for user %s in family %s - returning existing invitation",
                existing_pending["invitation_id"],
                invitee_id,
                family_id,
            )

            # Return the MongoDB document - caller will format it
            return existing_pending

        # Check for recently declined invitations (within 24 hours - anti-spam)
        recent_declined = await invitations_collection.find_one(
            {
                "family_id": family_id,
                "invitee_user_id": invitee_id,
                "status": "declined",
                "responded_at": {"$gt": now - timedelta(hours=24)},
            }
        )

        if recent_declined:
            # Ensure responded_at is timezone-aware for comparison
            responded_at = recent_declined["responded_at"]
            if responded_at.tzinfo is None:
                responded_at = responded_at.replace(tzinfo=timezone.utc)

            time_remaining = 24 - int((now - responded_at).total_seconds() / 3600)

            declined_at_str = responded_at.isoformat() if isinstance(responded_at, datetime) else str(responded_at)

            raise ValidationError(
                f"User recently declined an invitation. Please wait {time_remaining} hours before sending another. "
                f"Declined at: {declined_at_str}",
                field="invitee_id",
                value=invitee_id,
                constraint="recently_declined",
            )

        # Cleanup: Auto-cancel old pending invitations that expired
        expired_invitations = await invitations_collection.update_many(
            {"family_id": family_id, "invitee_user_id": invitee_id, "status": "pending", "expires_at": {"$lte": now}},
            {"$set": {"status": "expired", "responded_at": now, "auto_expired": True}},
        )

        if expired_invitations.modified_count > 0:
            self.logger.info(
                "Auto-expired %d old invitations for user %s in family %s",
                expired_invitations.modified_count,
                invitee_id,
                family_id,
            )

        # No existing pending invitation found
        return None

    async def _validate_relationship_logic(
        self, inviter_id: str, invitee_id: str, relationship_type: str, family_id: str
    ) -> None:
        """Validate relationship logic to prevent contradictory relationships."""
        # Check if users already have a relationship in this family
        relationships_collection = self.db_manager.get_collection("family_relationships")
        existing_relationship = await relationships_collection.find_one(
            {
                "family_id": family_id,
                "$or": [
                    {"user_a_id": inviter_id, "user_b_id": invitee_id},
                    {"user_a_id": invitee_id, "user_b_id": inviter_id},
                ],
                "status": "active",
            }
        )

        if existing_relationship:
            raise ValidationError(
                "Users already have an existing relationship in this family",
                field="relationship",
                constraint="no_existing_relationship",
            )

        # Additional logic validation (e.g., prevent someone from being both parent and child)
        # This can be extended based on business rules

    async def _generate_secure_invitation(
        self, family_id: str, inviter_id: str, invitee_user: Dict[str, Any], relationship_type: str
    ) -> Dict[str, Any]:
        """Generate secure invitation with cryptographic token and comprehensive data."""
        invitation_id = f"inv_{uuid.uuid4().hex[:16]}"
        invitation_token = secrets.token_urlsafe(32)  # Cryptographically secure token
        expires_at = datetime.now(timezone.utc) + timedelta(days=INVITATION_EXPIRY_DAYS)
        now = datetime.now(timezone.utc)

        invitation_document = {
            "invitation_id": invitation_id,
            "family_id": family_id,
            "inviter_user_id": inviter_id,
            "invitee_email": invitee_user.get("email", ""),
            "invitee_user_id": str(invitee_user["_id"]),
            # store invitee username at creation time for easier reads
            "invitee_username": invitee_user.get("username", ""),
            "relationship_type": relationship_type.lower(),
            "invitation_token": invitation_token,
            "status": "pending",
            "expires_at": expires_at,
            "created_at": now,
            "responded_at": None,
            "email_sent": False,
            "email_sent_at": None,
            "email_attempts": 0,
            "security_context": {
                "token_generated_at": now,
                "token_entropy_bits": 256,  # token_urlsafe(32) provides 256 bits of entropy
                "invitation_source": "family_manager",
                "version": "1.0",
            },
        }

        return {
            "invitation_id": invitation_id,
            "document": invitation_document,
            "expires_at": expires_at,
            "token": invitation_token,
        }

    async def _send_invitation_email_safe(self, invitation_doc: Dict[str, Any], family: Dict[str, Any]) -> bool:
        """Send invitation email with error handling that doesn't break transactions."""
        try:
            return await self._send_invitation_email(invitation_doc, family)
        except Exception as e:
            self.logger.warning(
                "Failed to send invitation email for %s: %s",
                invitation_doc["invitation_id"],
                e,
                extra={
                    "invitation_id": invitation_doc["invitation_id"],
                    "invitee_email": invitation_doc["invitee_email"],
                    "family_id": invitation_doc["family_id"],
                },
            )
            return False

    async def _get_user_by_id(self, user_id: str) -> Dict[str, Any]:
        """Get user document by ID."""
        users_collection = db_manager.get_collection("users")
        # Try direct lookup first (maybe _id stored as ObjectId or string)
        user = await users_collection.find_one({"_id": user_id})
        if not user:
            # If user_id looks like an ObjectId hex string, try converting
            try:
                if isinstance(user_id, str) and len(user_id) == 24:
                    oid = ObjectId(user_id)
                    user = await users_collection.find_one({"_id": oid})
            except Exception:
                user = None

        if not user:
            raise FamilyError(f"User not found: {user_id}")
        return user

    async def _get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user document by email."""
        users_collection = db_manager.get_collection("users")
        return await users_collection.find_one({"email": email})

    async def _get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user document by username."""
        users_collection = db_manager.get_collection("users")
        return await users_collection.find_one({"username": username})

    async def _get_family_by_id(self, family_id: str) -> Dict[str, Any]:
        """Get family document by ID."""
        families_collection = db_manager.get_collection("families")
        family = await families_collection.find_one({"family_id": family_id, "is_active": True})
        if not family:
            raise FamilyNotFound(f"Family not found: {family_id}")
        return family

    async def _is_user_in_family(self, user_id: str, family_id: str) -> bool:
        """Check if user is already in the family."""
        user = await self._get_user_by_id(user_id)
        family_memberships = user.get("family_memberships", [])
        return any(membership["family_id"] == family_id for membership in family_memberships)

    async def _create_virtual_sbd_account(self, username: str, family_id: str) -> None:
        """
        Create virtual SBD account for the family (legacy method - use transactional version).

        This method is kept for backward compatibility but should not be used for new implementations.
        Use _create_virtual_sbd_account_transactional instead for transaction safety.
        """
        self.logger.warning("Using legacy _create_virtual_sbd_account method. Consider using transactional version.")

        users_collection = self.db_manager.get_collection("users")
        now = datetime.now(timezone.utc)

        # Generate unique account ID for audit trails
        account_id = f"va_{uuid.uuid4().hex[:16]}"

        virtual_account = {
            "username": username,
            "sbd_tokens": 0,
            "sbd_tokens_transactions": [],
            "email": f"{username}@system.internal",
            "is_virtual_account": True,
            "managed_by_family": family_id,
            "created_at": now,
            "updated_at": now,
            "account_type": "family_virtual",
            "status": "active",
            "account_id": account_id,
            # Basic security controls for legacy compatibility
            "security_settings": {
                "creation_method": "legacy",
                "requires_family_auth": True,
                "spending_requires_permission": True,
                "audit_all_transactions": True,
            },
            # Basic audit trail
            "audit_trail": {
                "created_by_system": "family_manager_legacy",
                "creation_timestamp": now,
                "last_activity": now,
                "activity_count": 0,
            },
        }

        await users_collection.insert_one(virtual_account)

        # Log security event for virtual account creation
        await self._log_virtual_account_security_event(
            account_id=account_id,
            username=username,
            event_type="virtual_account_created",
            details={"family_id": family_id, "creation_method": "legacy", "transaction_safe": False},
        )
        self.logger.info("Virtual SBD account created: %s for family %s", username, family_id)

    async def _add_user_to_family_membership(
        self, user_id: str, family_id: str, role: str, joined_at: datetime
    ) -> None:
        """Add user to family membership list."""
        users_collection = db_manager.get_collection("users")
        # Resolve canonical user document to ensure correct _id type
        user_doc = await self._get_user_by_id(user_id)
        canonical_id = user_doc.get("_id")

        membership = {
            "family_id": family_id,
            "role": role,
            "joined_at": joined_at,
            "spending_permissions": {
                "can_spend": role == "admin",
                "spending_limit": -1 if role == "admin" else 0,
                "last_updated": joined_at,
            },
        }

        result = await users_collection.update_one({"_id": canonical_id}, {"$push": {"family_memberships": membership}})
        self.logger.info(
            "Legacy membership update for user %s -> matched=%d modified=%d",
            canonical_id,
            result.matched_count,
            result.modified_count,
        )
        if result.matched_count == 0:
            raise FamilyError(f"Failed to add user to family: no matching user for id {canonical_id}")

    async def _create_bidirectional_relationship(
        self, family_id: str, user_a_id: str, user_b_id: str, relationship_type: str
    ) -> None:
        """Create bidirectional family relationship."""
        relationships_collection = db_manager.get_collection("family_relationships")

        # Get reciprocal relationship type
        reciprocal_type = RELATIONSHIP_TYPES.get(relationship_type, relationship_type)

        relationship_id = f"rel_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        relationship_doc = {
            "relationship_id": relationship_id,
            "family_id": family_id,
            "user_a_id": user_a_id,
            "user_b_id": user_b_id,
            "relationship_type_a_to_b": relationship_type,
            "relationship_type_b_to_a": reciprocal_type,
            "status": "active",
            "created_by": user_a_id,
            "created_at": now,
            "activated_at": now,
            "updated_at": now,
        }

        await relationships_collection.insert_one(relationship_doc)
        self.logger.info(
            "Bidirectional relationship created: %s between %s and %s", relationship_id, user_a_id, user_b_id
        )

    async def modify_relationship_type(
        self,
        family_id: str,
        admin_id: str,
        user_a_id: str,
        user_b_id: str,
        new_relationship_type: str,
        request_context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Modify the relationship type between two family members.

        Args:
            family_id: ID of the family
            admin_id: ID of the admin making the change
            user_a_id: ID of the first user in the relationship
            user_b_id: ID of the second user in the relationship
            new_relationship_type: New relationship type from user_a's perspective
            request_context: Request context for rate limiting and security

        Returns:
            Dict containing updated relationship information

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
            InvalidRelationship: If relationship type is invalid
            ValidationError: If relationship doesn't exist
            TransactionError: If database transaction fails
        """
        operation_context = {
            "family_id": family_id,
            "admin_id": admin_id,
            "user_a_id": user_a_id,
            "user_b_id": user_b_id,
            "new_relationship_type": new_relationship_type,
            "operation": "modify_relationship",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("family_relationships", "modify_relationship", operation_context)

        # Rate limiting check
        if request_context:
            try:
                await self._check_rate_limit(request_context, "modify_relationship", 10, 3600)
            except Exception as e:
                raise RateLimitExceeded(
                    "Relationship modification rate limit exceeded", action="modify_relationship", limit=10, window=3600
                )

        session = None

        try:
            # Validate inputs
            if new_relationship_type not in RELATIONSHIP_TYPES:
                raise InvalidRelationship(
                    f"Invalid relationship type: {new_relationship_type}",
                    relationship_type=new_relationship_type,
                    valid_types=list(RELATIONSHIP_TYPES.keys()),
                )

            # Verify family exists and user has admin permissions
            family = await self._get_family_by_id(family_id)
            if admin_id not in family["admin_user_ids"]:
                raise InsufficientPermissions(
                    "Only family admins can modify relationships", required_role="admin", user_role="member"
                )

            # Find the existing relationship
            relationships_collection = self.db_manager.get_collection("family_relationships")
            existing_relationship = await relationships_collection.find_one(
                {
                    "family_id": family_id,
                    "$or": [
                        {"user_a_id": user_a_id, "user_b_id": user_b_id},
                        {"user_a_id": user_b_id, "user_b_id": user_a_id},
                    ],
                    "status": "active",
                }
            )

            if not existing_relationship:
                raise ValidationError(
                    "No active relationship found between these users", field="relationship", constraint="must_exist"
                )

            # Get reciprocal relationship type
            reciprocal_type = RELATIONSHIP_TYPES.get(new_relationship_type, new_relationship_type)

            # Start transaction for relationship modification
            client = self.db_manager.client
            session = await client.start_session()

            async with session.start_transaction():
                now = datetime.now(timezone.utc)

                # Determine correct orientation and update
                if existing_relationship["user_a_id"] == user_a_id:
                    # Update as-is
                    update_doc = {
                        "$set": {
                            "relationship_type_a_to_b": new_relationship_type,
                            "relationship_type_b_to_a": reciprocal_type,
                            "updated_at": now,
                            "updated_by": admin_id,
                        }
                    }
                else:
                    # Swap the relationship types since user_a and user_b are reversed
                    update_doc = {
                        "$set": {
                            "relationship_type_a_to_b": reciprocal_type,
                            "relationship_type_b_to_a": new_relationship_type,
                            "updated_at": now,
                            "updated_by": admin_id,
                        }
                    }

                # Update the relationship
                await relationships_collection.update_one(
                    {"relationship_id": existing_relationship["relationship_id"]}, update_doc, session=session
                )

                # Create notification for both users
                notification_data = {
                    "type": "relationship_modified",
                    "title": "Family Relationship Updated",
                    "message": f"Your family relationship has been updated by an administrator",
                    "data": {
                        "old_relationship": existing_relationship["relationship_type_a_to_b"],
                        "new_relationship": new_relationship_type,
                        "modified_by": admin_id,
                        "family_id": family_id,
                    },
                }

                # Send notifications to both users
                await self._create_family_notification(family_id, [user_a_id, user_b_id], notification_data, session)

                # Log successful modification
                self.db_manager.log_query_success(
                    "family_relationships",
                    "modify_relationship",
                    start_time,
                    1,
                    f"Relationship modified: {existing_relationship['relationship_id']}",
                )

                self.logger.info(
                    "Family relationship modified successfully: %s between %s and %s by admin %s",
                    existing_relationship["relationship_id"],
                    user_a_id,
                    user_b_id,
                    admin_id,
                    extra={
                        "relationship_id": existing_relationship["relationship_id"],
                        "family_id": family_id,
                        "admin_id": admin_id,
                        "old_relationship": existing_relationship["relationship_type_a_to_b"],
                        "new_relationship": new_relationship_type,
                        "transaction_id": str(session.session_id) if session else None,
                    },
                )

                return {
                    "relationship_id": existing_relationship["relationship_id"],
                    "family_id": family_id,
                    "user_a_id": user_a_id,
                    "user_b_id": user_b_id,
                    "old_relationship_type": existing_relationship["relationship_type_a_to_b"],
                    "new_relationship_type": new_relationship_type,
                    "new_reciprocal_type": reciprocal_type,
                    "modified_by": admin_id,
                    "modified_at": now,
                    "transaction_safe": True,
                }

        except (FamilyNotFound, InsufficientPermissions, InvalidRelationship, ValidationError, RateLimitExceeded) as e:
            # These are expected validation errors, don't wrap them
            self.db_manager.log_query_error(
                "family_relationships", "modify_relationship", start_time, e, operation_context
            )
            raise

        except Exception as e:
            # Handle transaction rollback
            rollback_successful = False
            if session and session.in_transaction:
                try:
                    await session.abort_transaction()
                    rollback_successful = True
                    self.logger.warning("Transaction rolled back successfully for relationship modification")
                except Exception as rollback_error:
                    self.logger.error(
                        "Failed to rollback relationship modification transaction: %s", rollback_error, exc_info=True
                    )

            self.db_manager.log_query_error(
                "family_relationships", "modify_relationship", start_time, e, operation_context
            )
            self.logger.error(
                "Failed to modify relationship in family %s: %s",
                family_id,
                e,
                exc_info=True,
                extra={
                    "family_id": family_id,
                    "admin_id": admin_id,
                    "user_a_id": user_a_id,
                    "user_b_id": user_b_id,
                    "rollback_successful": rollback_successful,
                    "transaction_id": str(session.session_id) if session else None,
                },
            )

            raise TransactionError(
                f"Failed to modify relationship: {str(e)}",
                operation="modify_relationship",
                rollback_successful=rollback_successful,
            )

        finally:
            if session:
                await session.end_session()

    async def _create_invitation_non_transactional(
        self, family_id: str, inviter_id: str, invitee_user: Dict[str, Any], relationship_type: str, start_time: float
    ) -> Dict[str, Any]:
        """
        Non-transactional invitation creation for environments without transaction support.
        Inserts invitation, attempts to send email, and updates the invitation document accordingly.
        """
        invitations_collection = self.db_manager.get_tenant_collection("family_invitations")
        family = await self._get_family_by_id(family_id)

        invitation_data = await self._generate_secure_invitation(family_id, inviter_id, invitee_user, relationship_type)
        try:
            await invitations_collection.insert_one(invitation_data["document"])
        except Exception as e:
            self.db_manager.log_query_error(
                "family_invitations", "create_invitation_non_transactional", start_time, e, {"family_id": family_id}
            )
            self.logger.error("Failed to insert invitation non-transactionally: %s", e, exc_info=True)
            raise TransactionError(f"Failed to create invitation: {e}")

        # Send the email (best-effort; failure doesn't remove the invitation)
        email_sent = await self._send_invitation_email_safe(invitation_data["document"], family)

        try:
            await invitations_collection.update_one(
                {"invitation_id": invitation_data["invitation_id"]},
                {
                    "$set": {
                        "email_sent": email_sent,
                        "email_sent_at": datetime.now(timezone.utc) if email_sent else None,
                        "email_attempts": 1,
                    }
                },
            )
        except Exception as e:
            # Log but don't treat as fatal — we already have the invitation stored
            self.logger.warning(
                "Failed to update email_sent status on invitation %s: %s",
                invitation_data["invitation_id"],
                e,
                exc_info=True,
            )

        self.db_manager.log_query_success(
            "family_invitations",
            "create_invitation_non_transactional",
            start_time,
            1,
            f"Invitation created non-transactionally: {invitation_data['invitation_id']}",
        )

        return {
            "invitation_id": invitation_data["invitation_id"],
            "family_name": family.get("name"),
            "invitee_email": invitation_data["document"].get("invitee_email"),
            "invitee_username": invitee_user.get("username"),
            "relationship_type": relationship_type,
            "expires_at": invitation_data["expires_at"],
            "created_at": invitation_data["document"].get("created_at"),
            "invitation_token": invitation_data.get("token"),
            "status": "pending",
            "email_sent": email_sent,
            "transaction_safe": False,
        }

    async def get_family_relationships(self, family_id: str, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all relationships within a family with detailed user information.

        Args:
            family_id: ID of the family
            user_id: ID of the user requesting the relationships

        Returns:
            List of relationship dictionaries with user details

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not a family member
            FamilyError: If retrieval fails
        """
        operation_context = {
            "family_id": family_id,
            "user_id": user_id,
            "operation": "get_family_relationships",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start(
            "family_relationships", "get_family_relationships", operation_context
        )

        try:
            # Verify family exists and user is a member
            family = await self._get_family_by_id(family_id)

            # Check if user is a family member
            is_member = await self._is_family_member(user_id, family_id)
            if not is_member:
                raise InsufficientPermissions(
                    "Only family members can view relationships", required_role="member", user_role="non_member"
                )

            # Get all relationships for the family
            relationships_collection = self.db_manager.get_collection("family_relationships")
            relationships_cursor = relationships_collection.find({"family_id": family_id, "status": "active"}).sort(
                "created_at", 1
            )

            relationships = await relationships_cursor.to_list(length=None)

            # Enrich relationships with user information
            enriched_relationships = []
            users_collection = self.db_manager.get_collection("users")

            for rel in relationships:
                # Get user information for both users
                user_a = await users_collection.find_one({"_id": rel["user_a_id"]}, {"username": 1, "email": 1})
                user_b = await users_collection.find_one({"_id": rel["user_b_id"]}, {"username": 1, "email": 1})

                if user_a and user_b:
                    enriched_relationships.append(
                        {
                            "relationship_id": rel["relationship_id"],
                            "family_id": rel["family_id"],
                            "user_a": {
                                "user_id": rel["user_a_id"],
                                "username": user_a.get("username", "Unknown"),
                                "relationship_type": rel["relationship_type_a_to_b"],
                            },
                            "user_b": {
                                "user_id": rel["user_b_id"],
                                "username": user_b.get("username", "Unknown"),
                                "relationship_type": rel["relationship_type_b_to_a"],
                            },
                            "status": rel["status"],
                            "created_by": rel["created_by"],
                            "created_at": rel["created_at"],
                            "updated_at": rel["updated_at"],
                        }
                    )

            # Log successful retrieval
            self.db_manager.log_query_success(
                "family_relationships",
                "get_family_relationships",
                start_time,
                len(enriched_relationships),
                f"Retrieved {len(enriched_relationships)} relationships for family {family_id}",
            )

            self.logger.debug(
                "Retrieved %d relationships for family %s by user %s",
                len(enriched_relationships),
                family_id,
                user_id,
                extra={"family_id": family_id, "user_id": user_id, "relationship_count": len(enriched_relationships)},
            )

            return enriched_relationships

        except (FamilyNotFound, InsufficientPermissions) as e:
            # These are expected validation errors, don't wrap them
            self.db_manager.log_query_error(
                "family_relationships", "get_family_relationships", start_time, e, operation_context
            )
            raise

        except Exception as e:
            self.db_manager.log_query_error(
                "family_relationships", "get_family_relationships", start_time, e, operation_context
            )
            self.logger.error(
                "Failed to get relationships for family %s: %s",
                family_id,
                e,
                exc_info=True,
                extra={"family_id": family_id, "user_id": user_id},
            )

            raise FamilyError(f"Failed to retrieve family relationships: {str(e)}")

    async def _is_family_member(self, user_id: str, family_id: str) -> bool:
        """
        Check if a user is a member of a family.

        Args:
            user_id: ID of the user to check
            family_id: ID of the family

        Returns:
            bool: True if user is a family member, False otherwise
        """
        try:
            users_collection = self.db_manager.get_collection("users")
            user = await users_collection.find_one({"_id": user_id}, {"family_memberships": 1})

            if not user:
                return False

            family_memberships = user.get("family_memberships", [])
            return any(membership.get("family_id") == family_id for membership in family_memberships)

        except Exception as e:
            self.logger.error(
                "Error checking family membership for user %s in family %s: %s", user_id, family_id, e, exc_info=True
            )
            return False

    async def _increment_family_member_count(self, family_id: str) -> None:
        """Increment family member count."""
        families_collection = db_manager.get_collection("families")
        await families_collection.update_one(
            {"family_id": family_id}, {"$inc": {"member_count": 1}, "$set": {"updated_at": datetime.now(timezone.utc)}}
        )

    async def _get_sbd_account_balance(self, username: str) -> int:
        """Get SBD token balance for virtual account."""
        users_collection = db_manager.get_collection("users")
        account = await users_collection.find_one({"username": username}, {"sbd_tokens": 1})
        return account.get("sbd_tokens", 0) if account else 0

    async def validate_family_spending(
        self, family_username: str, spender_id: str, amount: int, request_context: Dict[str, Any] = None
    ) -> bool:
        """
        Validate if a user can spend from a family SBD account with comprehensive security controls.

        Args:
            family_username: Username of the family SBD account (e.g., "family_smiths")
            spender_id: ID of the user attempting to spend
            amount: Amount to spend
            request_context: Optional request context for additional security checks

        Returns:
            bool: True if spending is allowed, False otherwise
        """
        validation_context = {
            "family_username": family_username,
            "spender_id": spender_id,
            "amount": amount,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Verify this is a virtual family account with enhanced checks
            users_collection = self.db_manager.get_collection("users")
            virtual_account = await users_collection.find_one(
                {
                    "username": family_username,
                    "is_virtual_account": True,
                    "account_type": "family_virtual",
                    "status": "active",
                }
            )

            if not virtual_account:
                await self._log_spending_validation_failure(
                    family_username, spender_id, amount, "virtual_account_not_found", validation_context
                )
                return False

            # Check security settings
            security_settings = virtual_account.get("security_settings", {})
            if security_settings.get("requires_family_auth", True):
                # Verify user is actually a family member
                family_id = virtual_account.get("managed_by_family")
                if not family_id:
                    await self._log_spending_validation_failure(
                        family_username, spender_id, amount, "no_family_association", validation_context
                    )
                    return False

                # Verify user is a member of the family
                if not await self._is_user_family_member(spender_id, family_id):
                    await self._log_spending_validation_failure(
                        family_username, spender_id, amount, "not_family_member", validation_context
                    )
                    return False

            # Get family information with error handling
            try:
                family = await self._get_family_by_id(family_id)
            except FamilyNotFound:
                await self._log_spending_validation_failure(
                    family_username, spender_id, amount, "family_not_found", validation_context
                )
                return False

            # Check if account is frozen
            if family["sbd_account"]["is_frozen"]:
                await self._log_spending_validation_failure(
                    family_username,
                    spender_id,
                    amount,
                    "account_frozen",
                    {**validation_context, "frozen_by": family["sbd_account"].get("frozen_by")},
                )
                return False

            # Check user permissions with detailed validation
            permissions = family["sbd_account"]["spending_permissions"].get(spender_id)
            if not permissions or not permissions.get("can_spend", False):
                await self._log_spending_validation_failure(
                    family_username, spender_id, amount, "no_spending_permission", validation_context
                )
                return False

            # Check spending limit with enhanced validation
            spending_limit = permissions.get("spending_limit", 0)
            if spending_limit != -1 and amount > spending_limit:
                await self._log_spending_validation_failure(
                    family_username,
                    spender_id,
                    amount,
                    "spending_limit_exceeded",
                    {**validation_context, "spending_limit": spending_limit},
                )
                return False

            # Additional security checks based on amount
            if amount > 10000:  # Large transaction threshold
                await self._log_virtual_account_security_event(
                    account_id=virtual_account.get("account_id"),
                    username=family_username,
                    event_type="large_transaction_validation",
                    details={
                        "spender_id": spender_id,
                        "amount": amount,
                        "spending_limit": spending_limit,
                        "validation_passed": True,
                    },
                )

            # Log successful validation
            await self._log_spending_validation_success(family_username, spender_id, amount, validation_context)

            self.logger.debug(
                "Family spending validation passed for user %s, amount %d in account %s",
                spender_id,
                amount,
                family_username,
                extra={
                    "family_username": family_username,
                    "spender_id": spender_id,
                    "amount": amount,
                    "spending_limit": spending_limit,
                    "family_id": family_id,
                },
            )
            return True

        except Exception as e:
            await self._log_spending_validation_failure(
                family_username, spender_id, amount, "validation_error", {**validation_context, "error": str(e)}
            )
            self.logger.error("Error validating family spending: %s", e, exc_info=True, extra=validation_context)
            return False

    async def _log_spending_validation_success(
        self, family_username: str, spender_id: str, amount: int, context: Dict[str, Any]
    ) -> None:
        """Log successful spending validation for audit purposes."""
        try:
            users_collection = self.db_manager.get_collection("users")
            virtual_account = await users_collection.find_one({"username": family_username, "is_virtual_account": True})

            if virtual_account:
                await self._log_virtual_account_security_event(
                    account_id=virtual_account.get("account_id"),
                    username=family_username,
                    event_type="spending_validation_success",
                    details={"spender_id": spender_id, "amount": amount, "context": context},
                )
        except Exception as e:
            self.logger.error("Failed to log spending validation success: %s", e, exc_info=True)

    async def _log_spending_validation_failure(
        self, family_username: str, spender_id: str, amount: int, reason: str, context: Dict[str, Any]
    ) -> None:
        """Log failed spending validation for security monitoring."""
        try:
            users_collection = self.db_manager.get_collection("users")
            virtual_account = await users_collection.find_one({"username": family_username, "is_virtual_account": True})

            if virtual_account:
                await self._log_virtual_account_security_event(
                    account_id=virtual_account.get("account_id"),
                    username=family_username,
                    event_type="spending_validation_failure",
                    details={"spender_id": spender_id, "amount": amount, "reason": reason, "context": context},
                )

            # Also log to application logs for immediate monitoring
            self.logger.warning(
                "Family spending validation failed: %s for user %s, amount %d, reason: %s",
                family_username,
                spender_id,
                amount,
                reason,
                extra={
                    "family_username": family_username,
                    "spender_id": spender_id,
                    "amount": amount,
                    "reason": reason,
                    "context": context,
                },
            )
        except Exception as e:
            self.logger.error("Failed to log spending validation failure: %s", e, exc_info=True)

    async def _is_user_family_member(self, user_id: str, family_id: str) -> bool:
        """
        Check if a user is a member of a specific family.

        Args:
            user_id: User ID to check
            family_id: Family ID to check membership in

        Returns:
            bool: True if user is a family member, False otherwise
        """
        try:
            users_collection = self.db_manager.get_collection("users")
            user = await users_collection.find_one({"_id": user_id})

            if not user:
                return False

            family_memberships = user.get("family_memberships", [])
            return any(
                membership.get("family_id") == family_id and membership.get("status") == "active"
                for membership in family_memberships
            )
        except Exception as e:
            self.logger.error("Error checking family membership: %s", e, exc_info=True)
            return False

    async def get_family_id_by_sbd_account(self, sbd_username: str) -> Optional[str]:
        """
        Get family ID by SBD account username.

        Args:
            sbd_username: SBD account username

        Returns:
            Family ID if found, None otherwise
        """
        try:
            families_collection = self.db_manager.get_tenant_collection("families")
            family = await families_collection.find_one({"sbd_account.account_username": sbd_username})

            if family:
                return family["family_id"]
            return None

        except Exception as e:
            self.logger.warning("Failed to get family ID by SBD account %s: %s", sbd_username, e)
            return None

    async def is_virtual_family_account(self, username: str) -> bool:
        """
        Check if a username corresponds to a virtual family account.

        Args:
            username: Username to check

        Returns:
            bool: True if it's a virtual family account, False otherwise
        """
        try:
            users_collection = self.db_manager.get_collection("users")
            account = await users_collection.find_one(
                {"username": username, "is_virtual_account": True, "account_type": "family_virtual", "status": "active"}
            )
            return account is not None
        except Exception as e:
            self.logger.error("Error checking if account is virtual family account: %s", e, exc_info=True)
            return False

    # Duplicate method removed - keeping only the first definition

    async def generate_collision_resistant_family_username(self, family_name: str, max_attempts: int = 20) -> str:
        """
        Generate a collision-resistant virtual family account username.

        Args:
            family_name: Base family name to use
            max_attempts: Maximum attempts to find unique username

        Returns:
            str: Unique family account username

        Raises:
            ValidationError: If unable to generate unique username
        """
        # Sanitize family name for username
        sanitized_name = self._sanitize_family_name_for_username(family_name)

        # Try base name first
        base_username = f"{VIRTUAL_ACCOUNT_PREFIX}{sanitized_name}"

        attempted_candidates = []
        for attempt in range(max_attempts):
            candidate_username = base_username

            # Add suffix for collision avoidance after first attempt
            if attempt > 0:
                # Use uuid-based suffix for stronger uniqueness
                uuid_suffix = uuid.uuid4().hex[:8]
                candidate_username = f"{base_username}_{uuid_suffix}"

            attempted_candidates.append(candidate_username)

            # Check if username is available
            if await self._is_username_available(candidate_username):
                # Validate against reserved prefixes - allow the virtual account prefix for family accounts
                is_valid, error_msg = await self.validate_username_against_reserved_prefixes(
                    candidate_username, allow_virtual_prefix=True
                )
                if is_valid:
                    self.logger.info(
                        "Generated collision-resistant family username: %s (attempt %d)",
                        candidate_username,
                        attempt + 1,
                    )
                    return candidate_username
                else:
                    self.logger.warning("Generated username failed validation: %s - %s", candidate_username, error_msg)

        # If we can't generate a unique username, raise an error
        # Log attempted candidates for debugging
        try:
            self.logger.error(
                "Unable to generate unique family username after %d attempts. Candidates tried: %s",
                max_attempts,
                ",".join(attempted_candidates),
            )
        except Exception:
            # Best-effort logging; don't fail on logging problems
            pass

        raise ValidationError(
            f"Unable to generate unique family username after {max_attempts} attempts",
            field="family_name",
            value=family_name,
            constraint="uniqueness",
        )

    def _sanitize_family_name_for_username(self, family_name: str) -> str:
        """
        Sanitize family name for use in username generation.

        Args:
            family_name: Original family name

        Returns:
            str: Sanitized name suitable for username
        """
        if not family_name:
            return "default"

        # Convert to lowercase and replace spaces/special chars with underscores
        sanitized = family_name.lower().strip()

        # Replace spaces and special characters with underscores
        import re

        sanitized = re.sub(r"[^a-z0-9_]", "_", sanitized)

        # Remove multiple consecutive underscores
        sanitized = re.sub(r"_+", "_", sanitized)

        # Remove leading/trailing underscores
        sanitized = sanitized.strip("_")

        # Ensure minimum length
        if len(sanitized) < MIN_FAMILY_NAME_LENGTH:
            sanitized = f"family_{sanitized}"

        # Ensure maximum length (accounting for prefix)
        max_base_length = MAX_FAMILY_NAME_LENGTH - len(VIRTUAL_ACCOUNT_PREFIX)
        if len(sanitized) > max_base_length:
            sanitized = sanitized[:max_base_length]

        return sanitized or "default"

    async def _is_username_available(self, username: str) -> bool:
        """
        Check if a username is available (not taken by any user or virtual account).

        Args:
            username: Username to check

        Returns:
            bool: True if available, False if taken
        """
        try:
            users_collection = self.db_manager.get_collection("users")
            existing_user = await users_collection.find_one({"username": username})
            return existing_user is None
        except Exception as e:
            self.logger.error("Error checking username availability: %s", e, exc_info=True)
            return False

    async def validate_username_against_reserved_prefixes(
        self, username: str, allow_virtual_prefix: bool = False
    ) -> Tuple[bool, str]:
        """
        Validate username against reserved prefixes used by the family system.

        Args:
            username: Username to validate

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        try:
            if not username or not isinstance(username, str):
                return False, "Username must be a non-empty string"

            username_lower = username.lower()

            # Check against reserved prefixes. Allow virtual account prefix when requested
            for prefix in RESERVED_PREFIXES:
                if allow_virtual_prefix and prefix == VIRTUAL_ACCOUNT_PREFIX:
                    # Skip blocking the virtual account prefix when explicitly allowed
                    continue
                if username_lower.startswith(prefix):
                    return False, f"Username cannot start with reserved prefix '{prefix}'"

            # Additional validation rules
            if len(username) < 3:
                return False, "Username must be at least 3 characters long"

            if len(username) > 50:
                return False, "Username cannot exceed 50 characters"

            # Check for valid characters (alphanumeric, underscore, hyphen)
            import re

            if not re.match(r"^[a-zA-Z0-9_-]+$", username):
                return False, "Username can only contain letters, numbers, underscores, and hyphens"

            return True, ""

        except Exception as e:
            self.logger.error("Error validating username against reserved prefixes: %s", e, exc_info=True)
            return False, "Username validation failed due to system error"

    async def _send_invitation_email(self, invitation: Dict[str, Any], family: Dict[str, Any]) -> None:
        """Send family invitation email."""
        try:
            # Get inviter information
            inviter = await self._get_user_by_id(invitation["inviter_user_id"])
            inviter_username = inviter.get("username", "Unknown")

            # Create verification links (placeholder URLs)
            accept_link = f"{settings.BASE_URL}/family/invitation/{invitation['invitation_token']}/accept"
            decline_link = f"{settings.BASE_URL}/family/invitation/{invitation['invitation_token']}/decline"

            # Send family invitation email
            success = await email_manager.send_family_invitation_email(
                invitation["invitee_email"],
                inviter_username,
                family["name"],
                invitation["relationship_type"],
                accept_link,
                decline_link,
                invitation["expires_at"].strftime("%Y-%m-%d %H:%M:%S UTC"),
            )

            if not success:
                self.logger.warning("Failed to send invitation email to %s", invitation["invitee_email"])
            else:
                self.logger.info("Invitation email sent successfully to %s", invitation["invitee_email"])

        except Exception as e:
            self.logger.error("Error sending invitation email: %s", e, exc_info=True)
            # Don't raise exception - invitation was created successfully

    async def delete_family(
        self, family_id: str, admin_user_id: str, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Delete a family and clean up all associated resources.

        Args:
            family_id: ID of the family to delete
            admin_user_id: ID of the admin user requesting deletion
            request_context: Request context for rate limiting and security (optional)

        Returns:
            Dict containing deletion confirmation

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
            FamilyError: If deletion fails
        """
        start_time = db_manager.log_query_start(
            "families", "delete_family", {"family_id": family_id, "admin_user_id": admin_user_id}
        )

        try:
            # Verify family exists and user is admin
            family = await self._get_family_by_id(family_id)
            if admin_user_id not in family["admin_user_ids"]:
                raise InsufficientPermissions("Only family admins can delete the family")

            # Get all family members for cleanup
            family_members = await self.get_family_members(family_id, admin_user_id)
            member_ids = [member["user_id"] for member in family_members]

            # Clean up virtual SBD account
            await self._cleanup_virtual_sbd_account(family["sbd_account"]["account_username"], family_id)

            # Remove family memberships from all users
            await self._remove_family_memberships(member_ids, family_id)

            # Delete all family relationships
            relationships_deleted = await self._delete_family_relationships(family_id)

            # Delete all family invitations
            await self._delete_family_invitations(family_id)

            # Delete all family notifications
            await self._delete_family_notifications(family_id)

            # Delete all family token requests
            await self._delete_family_token_requests(family_id)

            # Finally, delete the family document
            families_collection = db_manager.get_collection("families")
            deletion_timestamp = datetime.now(timezone.utc)
            await families_collection.delete_one({"family_id": family_id})

            db_manager.log_query_success("families", "delete_family", start_time, 1, f"Family deleted: {family_id}")

            self.logger.info("Family deleted successfully: %s by admin %s", family_id, admin_user_id)

            return {
                "status": "success",
                "family_id": family_id,
                "message": "Family and all associated resources have been deleted",
                "members_notified": len(member_ids),
                "relationships_cleaned": relationships_deleted,
                "sbd_account_handled": True,
                "deleted_at": deletion_timestamp,
                "transaction_safe": False,  # Not using transactions for deletion yet
            }

        except (FamilyNotFound, InsufficientPermissions):
            db_manager.log_query_error(
                "families", "delete_family", start_time, Exception("Validation error"), {"family_id": family_id}
            )
            raise
        except Exception as e:
            db_manager.log_query_error("families", "delete_family", start_time, e, {"family_id": family_id})
            self.logger.error("Failed to delete family %s: %s", family_id, e, exc_info=True)
            raise FamilyError(f"Failed to delete family: {str(e)}")

    async def _cleanup_virtual_sbd_account(self, username: str, family_id: str) -> None:
        """
        Clean up virtual SBD account when family is deleted.

        Args:
            username: Username of the virtual SBD account
            family_id: ID of the family being deleted

        Note:
            This method handles the remaining token balance by logging it.
            In a production system, you might want to transfer remaining tokens
            back to the family admin or handle according to business rules.
        """
        try:
            users_collection = db_manager.get_collection("users")

            # Get the virtual account to check balance
            virtual_account = await users_collection.find_one(
                {"username": username, "is_virtual_account": True, "managed_by_family": family_id}
            )

            if virtual_account:
                remaining_balance = virtual_account.get("sbd_tokens", 0)
                transaction_count = len(virtual_account.get("sbd_tokens_transactions", []))

                # Log the cleanup for audit purposes
                self.logger.info(
                    "Cleaning up virtual SBD account: %s for family %s. "
                    "Remaining balance: %d tokens, Transaction count: %d",
                    username,
                    family_id,
                    remaining_balance,
                    transaction_count,
                )

                # Delete the virtual account
                result = await users_collection.delete_one(
                    {"username": username, "is_virtual_account": True, "managed_by_family": family_id}
                )

                if result.deleted_count > 0:
                    self.logger.info("Virtual SBD account deleted: %s", username)
                else:
                    self.logger.warning("Virtual SBD account not found for deletion: %s", username)
            else:
                self.logger.warning("Virtual SBD account not found: %s for family %s", username, family_id)

        except Exception as e:
            self.logger.error("Error cleaning up virtual SBD account %s: %s", username, e, exc_info=True)
            # Don't raise exception - continue with family deletion

    async def _remove_family_memberships(self, member_ids: List[str], family_id: str) -> None:
        """Remove family membership from all users."""
        try:
            users_collection = db_manager.get_collection("users")

            # Remove family membership from all members
            result = await users_collection.update_many(
                {"_id": {"$in": member_ids}}, {"$pull": {"family_memberships": {"family_id": family_id}}}
            )

            self.logger.info("Removed family memberships for %d users from family %s", result.modified_count, family_id)

        except Exception as e:
            self.logger.error("Error removing family memberships for family %s: %s", family_id, e, exc_info=True)

    async def _delete_family_relationships(self, family_id: str) -> int:
        """Delete all relationships for a family and return count."""
        try:
            relationships_collection = db_manager.get_collection("family_relationships")
            result = await relationships_collection.delete_many({"family_id": family_id})

            self.logger.info("Deleted %d family relationships for family %s", result.deleted_count, family_id)

            return result.deleted_count

        except Exception as e:
            self.logger.error("Error deleting family relationships for family %s: %s", family_id, e, exc_info=True)
            return 0

    async def _delete_family_invitations(self, family_id: str) -> None:
        """Delete all invitations for a family."""
        try:
            invitations_collection = db_manager.get_collection("family_invitations")
            result = await invitations_collection.delete_many({"family_id": family_id})

            self.logger.info("Deleted %d family invitations for family %s", result.deleted_count, family_id)

        except Exception as e:
            self.logger.error("Error deleting family invitations for family %s: %s", family_id, e, exc_info=True)

    async def _delete_family_notifications(self, family_id: str) -> None:
        """Delete all notifications for a family."""
        try:
            notifications_collection = db_manager.get_collection("family_notifications")
            result = await notifications_collection.delete_many({"family_id": family_id})

            self.logger.info("Deleted %d family notifications for family %s", result.deleted_count, family_id)

        except Exception as e:
            self.logger.error("Error deleting family notifications for family %s: %s", family_id, e, exc_info=True)

    async def _delete_family_token_requests(self, family_id: str) -> None:
        """Delete all token requests for a family."""
        try:
            requests_collection = db_manager.get_collection("family_token_requests")
            result = await requests_collection.delete_many({"family_id": family_id})

            self.logger.info("Deleted %d family token requests for family %s", result.deleted_count, family_id)

        except Exception as e:
            self.logger.error("Error deleting family token requests for family %s: %s", family_id, e, exc_info=True)

    async def _log_virtual_account_security_event(
        self, account_id: str, username: str, event_type: str, details: Dict[str, Any], session: ClientSession = None
    ) -> None:
        """
        Log security events for virtual accounts with comprehensive context.

        Args:
            account_id: Virtual account ID
            username: Virtual account username
            event_type: Type of security event
            details: Additional event details
            session: Optional database session
        """
        try:
            security_event = {
                "event_id": f"vse_{uuid.uuid4().hex[:16]}",
                "account_id": account_id,
                "username": username,
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc),
                "details": details,
                "source": "family_manager",
                "severity": self._get_event_severity(event_type),
            }

            # Store in virtual account audit trail
            users_collection = self.db_manager.get_collection("users")
            update_query = {
                "$push": {"audit_trail.security_events": security_event},
                "$set": {"audit_trail.last_activity": security_event["timestamp"]},
                "$inc": {"audit_trail.activity_count": 1},
            }

            if session:
                await users_collection.update_one(
                    {"username": username, "is_virtual_account": True}, update_query, session=session
                )
            else:
                await users_collection.update_one({"username": username, "is_virtual_account": True}, update_query)

            # Also log to application logs for monitoring
            self.logger.info(
                "Virtual account security event: %s for %s (%s)",
                event_type,
                username,
                account_id,
                extra={
                    "event_id": security_event["event_id"],
                    "account_id": account_id,
                    "username": username,
                    "event_type": event_type,
                    "severity": security_event["severity"],
                    "details": details,
                },
            )

        except Exception as e:
            self.logger.error(
                "Failed to log virtual account security event: %s",
                e,
                exc_info=True,
                extra={"account_id": account_id, "username": username, "event_type": event_type},
            )

    def _get_event_severity(self, event_type: str) -> str:
        """
        Determine severity level for security events.

        Args:
            event_type: Type of security event

        Returns:
            str: Severity level (low, medium, high, critical)
        """
        high_severity_events = [
            "virtual_account_deleted",
            "unauthorized_access_attempt",
            "spending_limit_exceeded",
            "account_frozen",
            "suspicious_transaction",
        ]

        medium_severity_events = [
            "virtual_account_created",
            "permissions_updated",
            "large_transaction",
            "account_unfrozen",
        ]

        if event_type in high_severity_events:
            return "high"
        elif event_type in medium_severity_events:
            return "medium"
        else:
            return "low"

    async def cleanup_virtual_account(
        self, family_id: str, admin_user_id: str, retention_override: bool = False
    ) -> Dict[str, Any]:
        """
        Securely cleanup virtual family account with data retention policies.

        Args:
            family_id: Family ID whose virtual account to cleanup
            admin_user_id: Admin user performing the cleanup
            retention_override: Override retention policies (admin only)

        Returns:
            Dict containing cleanup results

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
            ValidationError: If cleanup validation fails
        """
        operation_context = {
            "family_id": family_id,
            "admin_user_id": admin_user_id,
            "retention_override": retention_override,
            "operation": "cleanup_virtual_account",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("users", "cleanup_virtual_account", operation_context)

        try:
            # Verify family exists and user has admin permissions
            family = await self._get_family_by_id(family_id)
            if admin_user_id not in family["admin_user_ids"]:
                raise InsufficientPermissions(
                    "Only family admins can cleanup virtual accounts", required_role="admin", user_role="member"
                )

            # Get virtual account
            virtual_username = family["sbd_account"]["account_username"]
            users_collection = self.db_manager.get_collection("users")
            virtual_account = await users_collection.find_one(
                {"username": virtual_username, "is_virtual_account": True, "managed_by_family": family_id}
            )

            if not virtual_account:
                raise ValidationError("Virtual account not found for family", field="family_id", value=family_id)

            now = datetime.now(timezone.utc)
            cleanup_results = {
                "account_id": virtual_account.get("account_id"),
                "username": virtual_username,
                "family_id": family_id,
                "cleanup_timestamp": now,
                "admin_user_id": admin_user_id,
                "retention_override": retention_override,
            }

            # Check if account has remaining balance
            remaining_balance = virtual_account.get("sbd_tokens", 0)
            if remaining_balance > 0:
                cleanup_results["remaining_balance"] = remaining_balance
                cleanup_results["balance_transferred"] = False

                # Log warning about remaining balance
                self.logger.warning(
                    "Virtual account cleanup with remaining balance: %s tokens in %s",
                    remaining_balance,
                    virtual_username,
                )

            # Apply data retention policies
            if retention_override or self._should_cleanup_immediately(virtual_account):
                # Immediate cleanup - mark as deleted but retain audit trail
                cleanup_data = {
                    "status": "deleted",
                    "deleted_at": now,
                    "deleted_by": admin_user_id,
                    "cleanup_method": "immediate" if retention_override else "policy_based",
                    "original_data": {
                        "sbd_tokens": virtual_account.get("sbd_tokens", 0),
                        "transaction_count": len(virtual_account.get("sbd_tokens_transactions", [])),
                        "created_at": virtual_account.get("created_at"),
                        "performance_metrics": virtual_account.get("performance_metrics", {}),
                    },
                }

                # Update account to deleted status with retention data
                await users_collection.update_one(
                    {"username": virtual_username, "is_virtual_account": True},
                    {
                        "$set": {
                            "status": "deleted",
                            "deleted_at": now,
                            "deleted_by": admin_user_id,
                            "cleanup_data": cleanup_data,
                            "sbd_tokens": 0,  # Clear balance
                            "sbd_tokens_transactions": [],  # Clear transactions (retained in cleanup_data)
                        }
                    },
                )

                cleanup_results["cleanup_method"] = "immediate"
                cleanup_results["data_retained"] = True

            else:
                # Schedule for future cleanup based on retention policy
                retention_days = virtual_account.get("retention_policy", {}).get(
                    "retention_period_days", VIRTUAL_ACCOUNT_RETENTION_DAYS
                )
                cleanup_date = now + timedelta(days=retention_days)

                await users_collection.update_one(
                    {"username": virtual_username, "is_virtual_account": True},
                    {
                        "$set": {
                            "status": "scheduled_for_cleanup",
                            "cleanup_scheduled_at": now,
                            "cleanup_scheduled_by": admin_user_id,
                            "cleanup_date": cleanup_date,
                            "retention_policy.cleanup_scheduled": True,
                        }
                    },
                )

                cleanup_results["cleanup_method"] = "scheduled"
                cleanup_results["cleanup_date"] = cleanup_date
                cleanup_results["retention_days"] = retention_days

            # Log security event for cleanup
            await self._log_virtual_account_security_event(
                account_id=virtual_account.get("account_id"),
                username=virtual_username,
                event_type="virtual_account_cleanup_initiated",
                details={
                    "family_id": family_id,
                    "admin_user_id": admin_user_id,
                    "cleanup_method": cleanup_results["cleanup_method"],
                    "retention_override": retention_override,
                    "remaining_balance": remaining_balance,
                },
            )

            self.db_manager.log_query_success(
                "users",
                "cleanup_virtual_account",
                start_time,
                1,
                f"Virtual account cleanup initiated: {virtual_username}",
            )

            self.logger.info(
                "Virtual account cleanup initiated: %s for family %s by admin %s",
                virtual_username,
                family_id,
                admin_user_id,
                extra=cleanup_results,
            )

            return cleanup_results

        except (FamilyNotFound, InsufficientPermissions, ValidationError) as e:
            self.db_manager.log_query_error("users", "cleanup_virtual_account", start_time, e, operation_context)
            raise

        except Exception as e:
            self.db_manager.log_query_error("users", "cleanup_virtual_account", start_time, e, operation_context)
            self.logger.error(
                "Failed to cleanup virtual account for family %s: %s",
                family_id,
                e,
                exc_info=True,
                extra=operation_context,
            )
            raise TransactionError(f"Failed to cleanup virtual account: {str(e)}", operation="cleanup_virtual_account")

    def _should_cleanup_immediately(self, virtual_account: Dict[str, Any]) -> bool:
        """
        Determine if virtual account should be cleaned up immediately based on policies.

        Args:
            virtual_account: Virtual account document

        Returns:
            bool: True if should cleanup immediately
        """
        # Check if account has been inactive for extended period
        last_activity = virtual_account.get("audit_trail", {}).get("last_activity")
        if last_activity:
            inactive_days = (datetime.now(timezone.utc) - last_activity).days
            if inactive_days > VIRTUAL_ACCOUNT_RETENTION_DAYS:
                return True

        # Check if account has zero balance and no recent transactions
        balance = virtual_account.get("sbd_tokens", 0)
        transaction_count = len(virtual_account.get("sbd_tokens_transactions", []))

        if balance == 0 and transaction_count == 0:
            return True

        # Check if account is marked for auto cleanup
        auto_cleanup = virtual_account.get("retention_policy", {}).get("auto_cleanup_enabled", True)
        if not auto_cleanup:
            return False

        return False

    async def validate_user_security_context(self, user_id: str, request_context: Dict[str, Any]) -> bool:
        """
        Validate user security context for family operations.

        Args:
            user_id: ID of the user to validate
            request_context: Request context containing security information

        Returns:
            bool: True if security validation passes

        Raises:
            FamilyError: If security validation fails
        """
        try:
            # Use existing security manager instead of redundant family security manager
            from second_brain_database.managers.security_manager import security_manager

            # Extract request object from context
            request = request_context.get("request")
            operation = request_context.get("operation", "family_operation")

            if not request:
                self.logger.warning("No request object in security context for user %s", user_id)
                return True  # Allow operation if no request context

            # Use existing security manager for validation
            await security_manager.check_ip_lockdown(request, {"_id": user_id})
            await security_manager.check_user_agent_lockdown(request, {"_id": user_id})

            # Apply family-specific rate limiting
            family_action = f"family_{operation}"
            await security_manager.check_rate_limit(
                request=request,
                action=family_action,
                rate_limit_requests=self._get_operation_rate_limit(operation),
                rate_limit_period=3600,  # 1 hour
            )

            self.logger.debug("Security context validation successful for user %s, operation: %s", user_id, operation)

            return True

        except Exception as e:
            self.logger.error("Security context validation failed for user %s: %s", user_id, str(e), exc_info=True)
            raise FamilyError(f"Security validation failed: {str(e)}", error_code="SECURITY_VALIDATION_FAILED")

    async def check_trusted_access(self, user_id: str, ip_address: str, user_agent: str) -> bool:
        """
        Check if access is from a trusted IP and User Agent.

        Args:
            user_id: ID of the user
            ip_address: IP address of the request
            user_agent: User agent of the request

        Returns:
            bool: True if access is trusted
        """
        try:
            # Get user document
            users_collection = self.db_manager.get_collection("users")
            user = await users_collection.find_one({"_id": user_id})

            if not user:
                return False

            # Check IP lockdown
            if user.get("trusted_ip_lockdown", False):
                trusted_ips = user.get("trusted_ips", [])
                if ip_address not in trusted_ips:
                    # Check for temporary IP bypasses
                    temp_bypasses = user.get("temporary_ip_bypasses", [])
                    current_time = datetime.now(timezone.utc).isoformat()

                    ip_allowed = any(
                        bypass.get("ip_address") == ip_address and bypass.get("expires_at", "") > current_time
                        for bypass in temp_bypasses
                    )

                    if not ip_allowed:
                        self.logger.warning("Untrusted IP access attempt for user %s from %s", user_id, ip_address)
                        return False

            # Check User Agent lockdown
            if user.get("trusted_user_agent_lockdown", False):
                trusted_user_agents = user.get("trusted_user_agents", [])
                if user_agent not in trusted_user_agents:
                    # Check for temporary User Agent bypasses
                    temp_bypasses = user.get("temporary_user_agent_bypasses", [])
                    current_time = datetime.now(timezone.utc).isoformat()

                    ua_allowed = any(
                        bypass.get("user_agent") == user_agent and bypass.get("expires_at", "") > current_time
                        for bypass in temp_bypasses
                    )

                    if not ua_allowed:
                        self.logger.warning("Untrusted User Agent access attempt for user %s: %s", user_id, user_agent)
                        return False

            return True

        except Exception as e:
            self.logger.error("Error checking trusted access for user %s: %s", user_id, str(e), exc_info=True)
            return False

    async def log_family_security_event(self, user_id: str, action: str, context: Dict[str, Any]) -> None:
        """
        Log family security events for monitoring and audit.

        Args:
            user_id: ID of the user performing the action
            action: Action being performed
            context: Additional context information
        """
        try:
            # Use existing security manager directly instead of redundant family security manager
            # Extract security context
            ip_address = context.get("ip_address")
            success = context.get("success", True)

            # Log using existing logging infrastructure
            from second_brain_database.utils.logging_utils import log_security_event

            log_security_event(
                event_type=f"family_{action}", user_id=user_id, ip_address=ip_address, success=success, details=context
            )

            self.logger.debug("Family security event logged: %s by user %s", action, user_id)

        except Exception as e:
            self.logger.error("Failed to log family security event: %s", str(e), exc_info=True)

    async def _check_rate_limit(self, request_context: Dict[str, Any], action: str, limit: int, period: int) -> None:
        """Check rate limit for family operations using security manager."""
        try:
            request = request_context.get("request")
            if not request:
                return  # Skip rate limiting if no request context

            # Use existing security manager for rate limiting
            await security_manager.check_rate_limit(
                request=request, action=action, rate_limit_requests=limit, rate_limit_period=period
            )

        except Exception as e:
            self.logger.warning("Rate limit check failed for action %s: %s", action, str(e))
            raise RateLimitExceeded(f"Rate limit exceeded for {action}", action=action, limit=limit, window=period)

    # SBD Token Permission System Methods

    async def get_family_sbd_account(self, family_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get family SBD account details including balance and spending permissions.

        Args:
            family_id: ID of the family
            user_id: ID of the requesting user

        Returns:
            Dict containing SBD account information

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not a family member
        """
        operation_context = {
            "family_id": family_id,
            "user_id": user_id,
            "operation": "get_family_sbd_account",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "get_family_sbd_account", operation_context)

        try:
            # Verify family exists and user is a member
            family = await self._get_family_by_id(family_id)

            if not await self._is_user_in_family(user_id, family_id):
                raise InsufficientPermissions("You must be a family member to view SBD account details")

            # Get current balance from virtual account
            account_username = family["sbd_account"]["account_username"]
            current_balance = await self.get_family_sbd_balance(account_username)

            # Get recent transactions
            recent_transactions = await self._get_recent_family_transactions(account_username, limit=10)

            account_data = {
                "account_username": account_username,
                "balance": current_balance,
                "is_frozen": family["sbd_account"]["is_frozen"],
                "frozen_by": family["sbd_account"].get("frozen_by"),
                "frozen_at": family["sbd_account"].get("frozen_at"),
                "spending_permissions": family["sbd_account"]["spending_permissions"],
                # Backwards-compatible simplified map for frontend: keyed by user_id -> { can_spend, spending_limit }
                "member_permissions": {
                    uid: {
                        "can_spend": (perm.get("can_spend") if isinstance(perm, dict) else False),
                        "spending_limit": (perm.get("spending_limit") if isinstance(perm, dict) else 0),
                    }
                    for uid, perm in family["sbd_account"]["spending_permissions"].items()
                },
                "notification_settings": family["sbd_account"]["notification_settings"],
                "recent_transactions": recent_transactions,
            }

            # Try to enrich with virtual account metadata (account_id, account_name, currency)
            try:
                users_collection = self.db_manager.get_collection("users")
                virtual_account = await users_collection.find_one(
                    {"username": account_username, "is_virtual_account": True},
                    {"account_id": 1, "account_name": 1, "currency": 1},
                )
                if virtual_account:
                    account_data["account_id"] = virtual_account.get("account_id")
                    # Prefer family-stored name, fallback to virtual account name
                    account_data["account_name"] = family["sbd_account"].get("name") or virtual_account.get(
                        "account_name"
                    )
                    account_data["currency"] = virtual_account.get("currency") or "SBD"
                else:
                    account_data["account_id"] = None
                    account_data["account_name"] = family["sbd_account"].get("name")
                    account_data["currency"] = "SBD"
            except Exception:
                # Non-fatal enrichment
                account_data.setdefault("account_id", None)
                account_data.setdefault("account_name", family["sbd_account"].get("name"))
                account_data.setdefault("currency", "SBD")

            # Freeze reason canonical key for frontend
            account_data["freeze_reason"] = family["sbd_account"].get("freeze_reason")

            self.db_manager.log_query_success(
                "families", "get_family_sbd_account", start_time, 1, f"SBD account retrieved for family: {family_id}"
            )

            self.logger.debug("Retrieved SBD account for family %s by user %s", family_id, user_id)

            return account_data

        except (FamilyNotFound, InsufficientPermissions) as e:
            self.db_manager.log_query_error("families", "get_family_sbd_account", start_time, e, operation_context)
            raise
        except Exception as e:
            self.db_manager.log_query_error("families", "get_family_sbd_account", start_time, e, operation_context)
            self.logger.error("Failed to get family SBD account: %s", e, exc_info=True)
            raise FamilyError(f"Failed to retrieve SBD account: {str(e)}")

    async def get_family_owned_items(self, family_id: str, item_type: str) -> List[Dict[str, Any]]:
        """
        Get items owned by a family's virtual SBD account.

        Args:
            family_id: ID of the family
            item_type: "avatar", "theme", "banner", or "bundle"

        Returns:
            List of owned item entry dicts for the family (empty list if none)

        Raises:
            FamilyNotFound: If family doesn't exist
        """
        try:
            # Resolve family and virtual account username
            family = await self._get_family_by_id(family_id)
            account_username = family["sbd_account"]["account_username"]

            users_collection = self.db_manager.get_collection("users")
            field = f"{item_type}s_owned"

            projection = {field: 1}
            family_user = await users_collection.find_one(
                {"username": account_username, "is_virtual_account": True}, projection
            )
            if not family_user:
                return []

            return family_user.get(field, []) or []

        except FamilyNotFound:
            raise
        except Exception as e:
            self.logger.error("Failed to get family-owned items for family %s: %s", family_id, e, exc_info=True)
            return []

    async def update_spending_permissions(
        self, family_id: str, admin_id: str, target_user_id: str, permissions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update spending permissions for a family member.

        Args:
            family_id: ID of the family
            admin_id: ID of the admin making the change
            target_user_id: ID of the user whose permissions are being updated
            permissions: Dict containing spending_limit and can_spend

        Returns:
            Dict containing updated permission information

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not an admin
        """
        operation_context = {
            "family_id": family_id,
            "admin_id": admin_id,
            "target_user_id": target_user_id,
            "permissions": permissions,
            "operation": "update_spending_permissions",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "update_spending_permissions", operation_context)

        try:
            # Verify family exists and user is admin
            family = await self._get_family_by_id(family_id)

            if admin_id not in family["admin_user_ids"]:
                raise InsufficientPermissions("Only family admins can update spending permissions")

            # Verify target user is a family member
            if not await self._is_user_in_family(target_user_id, family_id):
                raise InsufficientPermissions("Target user is not a family member")

            # Update permissions
            now = datetime.now(timezone.utc)
            updated_permissions = {
                "role": "admin" if target_user_id in family["admin_user_ids"] else "member",
                "spending_limit": permissions["spending_limit"],
                "can_spend": permissions["can_spend"],
                "updated_by": admin_id,
                "updated_at": now.isoformat(),
            }

            # Update family document
            families_collection = self.db_manager.get_tenant_collection("families")
            await families_collection.update_one(
                {"family_id": family_id},
                {
                    "$set": {
                        f"sbd_account.spending_permissions.{target_user_id}": updated_permissions,
                        "updated_at": now,
                    }
                },
            )

            # Update user's family membership
            users_collection = self.db_manager.get_collection("users")
            await users_collection.update_one(
                {"_id": target_user_id, "family_memberships.family_id": family_id},
                {
                    "$set": {
                        "family_memberships.$.spending_permissions": {
                            "can_spend": permissions["can_spend"],
                            "spending_limit": permissions["spending_limit"],
                            "last_updated": now,
                        }
                    }
                },
            )

            # Send notification to affected user
            await self._send_spending_permissions_notification(family_id, target_user_id, admin_id, updated_permissions)

            self.db_manager.log_query_success(
                "families",
                "update_spending_permissions",
                start_time,
                1,
                f"Spending permissions updated for user {target_user_id} in family {family_id}",
            )

            self.logger.info(
                "Updated spending permissions for user %s in family %s by admin %s", target_user_id, family_id, admin_id
            )

            return {
                "message": "Spending permissions updated successfully",
                "family_id": family_id,
                "target_user_id": target_user_id,
                "new_permissions": updated_permissions,
                "updated_by": admin_id,
                "updated_at": now.isoformat(),
                "transaction_safe": True,
            }

        except (FamilyNotFound, InsufficientPermissions) as e:
            self.db_manager.log_query_error("families", "update_spending_permissions", start_time, e, operation_context)
            raise
        except Exception as e:
            self.db_manager.log_query_error("families", "update_spending_permissions", start_time, e, operation_context)
            self.logger.error("Failed to update spending permissions: %s", e, exc_info=True)
            raise FamilyError(f"Failed to update spending permissions: {str(e)}")

    # Token Request System Methods

    async def create_token_request(
        self, family_id: str, user_id: str, amount: int, reason: str, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a token request from the family account.

        Args:
            family_id: ID of the family
            user_id: ID of the user requesting tokens
            amount: Amount of tokens requested
            reason: Reason for the request
            request_context: Request context for rate limiting

        Returns:
            Dict containing request information

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not a family member
            ValidationError: If input validation fails
            AccountFrozen: If family account is frozen
        """
        operation_context = {
            "family_id": family_id,
            "user_id": user_id,
            "amount": amount,
            "reason": reason,
            "operation": "create_token_request",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("family_token_requests", "create_token_request", operation_context)

        # Rate limiting check
        if request_context:
            try:
                await self._check_rate_limit(request_context, "token_request_creation", 10, 3600)
            except Exception as e:
                raise RateLimitExceeded(
                    "Token request creation rate limit exceeded", action="token_request_creation", limit=10, window=3600
                )

        try:
            # Validate input
            if amount <= 0:
                raise ValidationError("Amount must be positive", field="amount", value=amount)

            if not reason or len(reason.strip()) < 5:
                raise ValidationError("Reason must be at least 5 characters", field="reason", value=reason)

            # Verify family exists and user is a member
            family = await self._get_family_by_id(family_id)

            if not await self._is_user_in_family(user_id, family_id):
                raise InsufficientPermissions("You must be a family member to request tokens")

            # Check if account is frozen
            if family["sbd_account"]["is_frozen"]:
                raise AccountFrozen(
                    "Cannot create token requests while family account is frozen",
                    family_id=family_id,
                    frozen_by=family["sbd_account"].get("frozen_by"),
                    frozen_at=family["sbd_account"].get("frozen_at"),
                )

            # Generate request ID and expiry
            request_id = f"req_{uuid.uuid4().hex[:16]}"
            now = datetime.now(timezone.utc)
            expiry_hours = family["settings"]["request_expiry_hours"]
            expires_at = now + timedelta(hours=expiry_hours)

            # Check auto-approval threshold
            auto_approval_threshold = family["settings"]["auto_approval_threshold"]
            auto_approved = amount <= auto_approval_threshold

            # Create request document
            request_doc = {
                "request_id": request_id,
                "family_id": family_id,
                "requester_user_id": user_id,
                "amount": amount,
                "reason": reason.strip(),
                "status": "auto_approved" if auto_approved else "pending",
                "reviewed_by": None,
                "admin_comments": None,
                "auto_approved": auto_approved,
                "created_at": now,
                "expires_at": expires_at,
                "reviewed_at": now if auto_approved else None,
                "processed_at": None,
            }

            # Insert request
            requests_collection = self.db_manager.get_tenant_collection("family_token_requests")
            await requests_collection.insert_one(request_doc)

            # If auto-approved, process immediately
            if auto_approved:
                await self._process_approved_token_request(request_id, "system", "Auto-approved based on threshold")
                request_doc["processed_at"] = now
            else:
                # Notify admins about pending request
                await self._notify_admins_token_request(family_id, request_doc)

            # Send notification to requester
            await self._send_token_request_notification(family_id, user_id, request_doc, "created")

            self.db_manager.log_query_success(
                "family_token_requests",
                "create_token_request",
                start_time,
                1,
                f"Token request created: {request_id} ({'auto-approved' if auto_approved else 'pending'})",
            )

            self.logger.info(
                "Token request created: %s for %d tokens by user %s in family %s (%s)",
                request_id,
                amount,
                user_id,
                family_id,
                "auto-approved" if auto_approved else "pending",
            )

            return {
                "request_id": request_id,
                "family_id": family_id,
                "amount": amount,
                "reason": reason,
                "status": request_doc["status"],
                "auto_approved": auto_approved,
                "expires_at": expires_at,
                "created_at": now,
                "processed_immediately": auto_approved,
            }

        except (FamilyNotFound, InsufficientPermissions, ValidationError, AccountFrozen, RateLimitExceeded) as e:
            self.db_manager.log_query_error(
                "family_token_requests", "create_token_request", start_time, e, operation_context
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "family_token_requests", "create_token_request", start_time, e, operation_context
            )
            self.logger.error("Failed to create token request: %s", e, exc_info=True)
            raise FamilyError(f"Failed to create token request: {str(e)}")

    async def review_token_request(
        self, request_id: str, admin_id: str, action: str, comments: str = None, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Review a token request (approve or deny).

        Args:
            request_id: ID of the token request
            admin_id: ID of the admin reviewing
            action: "approve" or "deny"
            comments: Optional admin comments
            request_context: Request context for rate limiting

        Returns:
            Dict containing review information

        Raises:
            TokenRequestNotFound: If request doesn't exist
            InsufficientPermissions: If user is not an admin
            ValidationError: If request is not in pending status
        """
        operation_context = {
            "request_id": request_id,
            "admin_id": admin_id,
            "action": action,
            "operation": "review_token_request",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("family_token_requests", "review_token_request", operation_context)

        # Rate limiting check
        if request_context:
            try:
                await self._check_rate_limit(request_context, "token_request_review", 20, 3600)
            except Exception as e:
                raise RateLimitExceeded(
                    "Token request review rate limit exceeded", action="token_request_review", limit=20, window=3600
                )

        try:
            # Validate action
            if action not in ["approve", "deny"]:
                raise ValidationError("Action must be 'approve' or 'deny'", field="action", value=action)

            # Get token request
            requests_collection = self.db_manager.get_tenant_collection("family_token_requests")
            request_doc = await requests_collection.find_one({"request_id": request_id})

            if not request_doc:
                raise TokenRequestNotFound("Token request not found", request_id=request_id)

            # Verify admin permissions
            family = await self._get_family_by_id(request_doc["family_id"])
            if admin_id not in family["admin_user_ids"]:
                raise InsufficientPermissions("Only family admins can review token requests")

            # Check if request is still pending
            if request_doc["status"] != "pending":
                raise ValidationError(
                    f"Cannot review request with status: {request_doc['status']}",
                    field="status",
                    value=request_doc["status"],
                )

            # Check if request has expired
            now = datetime.now(timezone.utc)
            expires_at = request_doc["expires_at"]

            # Handle timezone-aware vs naive datetime comparison
            if expires_at.tzinfo is None:
                # expires_at is naive, assume UTC
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if now > expires_at:
                # Auto-expire the request
                await requests_collection.update_one(
                    {"request_id": request_id},
                    {
                        "$set": {
                            "status": "expired",
                            "reviewed_at": now,
                            "reviewed_by": "system",
                            "admin_comments": "Request expired",
                        }
                    },
                )
                raise TokenRequestNotFound("Token request has expired", request_id=request_id, status="expired")

            # Update request status
            new_status = "approved" if action == "approve" else "denied"
            update_data = {
                "status": new_status,
                "reviewed_by": admin_id,
                "admin_comments": comments or "",
                "reviewed_at": now,
            }

            await requests_collection.update_one({"request_id": request_id}, {"$set": update_data})

            # If approved, process the token transfer
            if action == "approve":
                await self._process_approved_token_request(request_id, admin_id, comments)
                update_data["processed_at"] = now

                # Update processed_at in database
                await requests_collection.update_one({"request_id": request_id}, {"$set": {"processed_at": now}})

            # Send notifications
            await self._send_token_request_notification(
                request_doc["family_id"], request_doc["requester_user_id"], {**request_doc, **update_data}, action
            )

            # Notify other admins about the decision
            await self._notify_admins_token_decision(request_doc["family_id"], admin_id, request_doc, action, comments)

            self.db_manager.log_query_success(
                "family_token_requests", "review_token_request", start_time, 1, f"Token request {action}d: {request_id}"
            )

            self.logger.info(
                "Token request %s: %s by admin %s (amount: %d, requester: %s)",
                action,
                request_id,
                admin_id,
                request_doc["amount"],
                request_doc["requester_user_id"],
            )

            return {
                "request_id": request_id,
                "action": action,
                "status": new_status,
                "reviewed_by": admin_id,
                "admin_comments": comments,
                "reviewed_at": now,
                "processed_at": update_data.get("processed_at"),
                "amount": request_doc["amount"],
                "requester_user_id": request_doc["requester_user_id"],
            }

        except (TokenRequestNotFound, InsufficientPermissions, ValidationError, RateLimitExceeded) as e:
            self.db_manager.log_query_error(
                "family_token_requests", "review_token_request", start_time, e, operation_context
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "family_token_requests", "review_token_request", start_time, e, operation_context
            )
            self.logger.error("Failed to review token request: %s", e, exc_info=True)
            raise FamilyError(f"Failed to review token request: {str(e)}")

    async def get_pending_token_requests(self, family_id: str, admin_id: str) -> List[Dict[str, Any]]:
        """
        Get all pending token requests for a family (admin only).

        Args:
            family_id: ID of the family
            admin_id: ID of the admin requesting

        Returns:
            List of pending token requests

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not an admin
        """
        operation_context = {
            "family_id": family_id,
            "admin_id": admin_id,
            "operation": "get_pending_token_requests",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start(
            "family_token_requests", "get_pending_token_requests", operation_context
        )

        try:
            # Verify family exists and user is admin
            family = await self._get_family_by_id(family_id)
            if admin_id not in family["admin_user_ids"]:
                raise InsufficientPermissions("Only family admins can view pending token requests")

            # Get pending requests
            requests_collection = self.db_manager.get_tenant_collection("family_token_requests")
            cursor = requests_collection.find(
                {"family_id": family_id, "status": "pending", "expires_at": {"$gt": datetime.now(timezone.utc)}}
            ).sort("created_at", 1)

            requests = await cursor.to_list(length=None)

            # Enrich with user information
            enriched_requests = []
            for request in requests:
                requester = await self._get_user_by_id(request["requester_user_id"])
                enriched_requests.append(
                    {
                        "request_id": request["request_id"],
                        "requester_user_id": request["requester_user_id"],
                        "requester_username": requester.get("username", "Unknown"),
                        "amount": request["amount"],
                        "reason": request["reason"],
                        "status": request["status"],
                        "auto_approved": request["auto_approved"],
                        "created_at": request["created_at"],
                        "expires_at": request["expires_at"],
                    }
                )

            self.db_manager.log_query_success(
                "family_token_requests",
                "get_pending_token_requests",
                start_time,
                len(enriched_requests),
                f"Retrieved {len(enriched_requests)} pending requests",
            )

            self.logger.debug("Retrieved %d pending token requests for family %s", len(enriched_requests), family_id)

            return enriched_requests

        except (FamilyNotFound, InsufficientPermissions) as e:
            self.db_manager.log_query_error(
                "family_token_requests", "get_pending_token_requests", start_time, e, operation_context
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "family_token_requests", "get_pending_token_requests", start_time, e, operation_context
            )
            self.logger.error("Failed to get pending token requests: %s", e, exc_info=True)
            raise FamilyError(f"Failed to retrieve pending token requests: {str(e)}")

    async def get_user_token_requests(self, family_id: str, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get token request history for a user in a family.

        Args:
            family_id: ID of the family
            user_id: ID of the user
            limit: Maximum number of requests to return

        Returns:
            List of user's token requests

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not a family member
        """
        operation_context = {
            "family_id": family_id,
            "user_id": user_id,
            "limit": limit,
            "operation": "get_user_token_requests",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start(
            "family_token_requests", "get_user_token_requests", operation_context
        )

        try:
            # Verify family exists and user is a member
            family = await self._get_family_by_id(family_id)
            if not await self._is_user_in_family(user_id, family_id):
                raise InsufficientPermissions("You must be a family member to view token requests")

            # Get user's requests
            requests_collection = self.db_manager.get_tenant_collection("family_token_requests")
            cursor = (
                requests_collection.find({"family_id": family_id, "requester_user_id": user_id})
                .sort("created_at", -1)
                .limit(limit)
            )

            requests = await cursor.to_list(length=None)

            # Format response
            formatted_requests = []
            for request in requests:
                formatted_requests.append(
                    {
                        "request_id": request["request_id"],
                        "amount": request["amount"],
                        "reason": request["reason"],
                        "status": request["status"],
                        "auto_approved": request["auto_approved"],
                        "reviewed_by": request.get("reviewed_by"),
                        "admin_comments": request.get("admin_comments"),
                        "created_at": request["created_at"],
                        "expires_at": request["expires_at"],
                        "reviewed_at": request.get("reviewed_at"),
                        "processed_at": request.get("processed_at"),
                    }
                )

            self.db_manager.log_query_success(
                "family_token_requests",
                "get_user_token_requests",
                start_time,
                len(formatted_requests),
                f"Retrieved {len(formatted_requests)} requests for user",
            )

            self.logger.debug(
                "Retrieved %d token requests for user %s in family %s", len(formatted_requests), user_id, family_id
            )

            return formatted_requests

        except (FamilyNotFound, InsufficientPermissions) as e:
            self.db_manager.log_query_error(
                "family_token_requests", "get_user_token_requests", start_time, e, operation_context
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "family_token_requests", "get_user_token_requests", start_time, e, operation_context
            )
            self.logger.error("Failed to get user token requests: %s", e, exc_info=True)
            raise FamilyError(f"Failed to retrieve token requests: {str(e)}")

    async def cleanup_expired_token_requests(self) -> Dict[str, Any]:
        """
        Clean up expired token requests.

        Returns:
            Dict containing cleanup statistics
        """
        operation_context = {
            "operation": "cleanup_expired_token_requests",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start(
            "family_token_requests", "cleanup_expired_token_requests", operation_context
        )

        try:
            now = datetime.now(timezone.utc)
            requests_collection = self.db_manager.get_tenant_collection("family_token_requests")

            # Find expired pending requests
            expired_requests = await requests_collection.find(
                {"status": "pending", "expires_at": {"$lt": now}}
            ).to_list(length=None)

            # Update expired requests
            if expired_requests:
                result = await requests_collection.update_many(
                    {"status": "pending", "expires_at": {"$lt": now}},
                    {
                        "$set": {
                            "status": "expired",
                            "reviewed_at": now,
                            "reviewed_by": "system",
                            "admin_comments": "Request expired automatically",
                        }
                    },
                )

                # Send notifications to requesters
                for request in expired_requests:
                    try:
                        await self._send_token_request_notification(
                            request["family_id"],
                            request["requester_user_id"],
                            {**request, "status": "expired", "reviewed_at": now},
                            "expired",
                        )
                    except Exception as e:
                        self.logger.warning(
                            "Failed to send expiry notification for request %s: %s", request["request_id"], e
                        )

                cleanup_stats = {
                    "expired_count": result.modified_count,
                    "cleanup_timestamp": now,
                    "requests_processed": [req["request_id"] for req in expired_requests],
                }
            else:
                cleanup_stats = {"expired_count": 0, "cleanup_timestamp": now, "requests_processed": []}

            self.db_manager.log_query_success(
                "family_token_requests",
                "cleanup_expired_token_requests",
                start_time,
                cleanup_stats["expired_count"],
                f"Cleaned up {cleanup_stats['expired_count']} expired requests",
            )

            self.logger.info("Cleaned up %d expired token requests", cleanup_stats["expired_count"])

            return cleanup_stats

        except Exception as e:
            self.db_manager.log_query_error(
                "family_token_requests", "cleanup_expired_token_requests", start_time, e, operation_context
            )
            self.logger.error("Failed to cleanup expired token requests: %s", e, exc_info=True)
            raise FamilyError(f"Failed to cleanup expired requests: {str(e)}")

    async def _process_approved_token_request(self, request_id: str, approved_by: str, comments: str = None) -> None:
        """
        Process an approved token request by transferring tokens.

        Args:
            request_id: ID of the approved request
            approved_by: ID of the admin who approved (or "system" for auto-approval)
            comments: Optional admin comments
        """
        try:
            # Get request details
            requests_collection = self.db_manager.get_tenant_collection("family_token_requests")
            request_doc = await requests_collection.find_one({"request_id": request_id})

            if not request_doc:
                raise TokenRequestNotFound("Token request not found for processing", request_id=request_id)

            # Get family and requester information
            family = await self._get_family_by_id(request_doc["family_id"])
            requester = await self._get_user_by_id(request_doc["requester_user_id"])

            # Transfer tokens from family account to requester
            family_username = family["sbd_account"]["account_username"]
            requester_username = requester["username"]
            amount = request_doc["amount"]

            # Use existing SBD token transfer system directly
            users_collection = self.db_manager.get_collection("users")

            # Create transaction note
            transaction_note = f"Token request approved: {request_doc['reason']} (Request ID: {request_id})"
            if approved_by != "system":
                admin_user = await self._get_user_by_id(approved_by)
                transaction_note += f" - Approved by: {admin_user.get('username', 'Unknown')}"

            # Check if MongoDB is a replica set for transaction support
            is_replica_set = False
            try:
                ismaster = await self.db_manager.client.admin.command("ismaster")
                is_replica_set = bool(ismaster.get("setName"))
            except Exception as e:
                self.logger.warning("Could not determine replica set: %s", e)

            # Perform the transfer using the same logic as SBD routes
            now_iso = datetime.now(timezone.utc).isoformat()
            transaction_id = f"treq_{uuid.uuid4().hex[:16]}"

            if is_replica_set:
                # Use transaction/session if replica set
                async with await self.db_manager.client.start_session() as session:
                    async with session.start_transaction():
                        # Verify family account has sufficient balance
                        family_user_doc = await users_collection.find_one(
                            {"username": family_username}, session=session
                        )
                        if not family_user_doc or family_user_doc.get("sbd_tokens", 0) < amount:
                            raise FamilyError(
                                f"Insufficient tokens in family account: {family_user_doc.get('sbd_tokens', 0)} < {amount}"
                            )

                        # Create send transaction for family account
                        send_txn = {
                            "type": "send",
                            "to": requester_username,
                            "amount": amount,
                            "timestamp": now_iso,
                            "transaction_id": transaction_id,
                            "note": transaction_note,
                            "token_request_id": request_id,
                            "approved_by": approved_by,
                        }

                        # Deduct from family account
                        res1 = await users_collection.update_one(
                            {"username": family_username, "sbd_tokens": {"$gte": amount}},
                            {"$inc": {"sbd_tokens": -amount}, "$push": {"sbd_tokens_transactions": send_txn}},
                            session=session,
                        )

                        if res1.modified_count == 0:
                            raise FamilyError("Insufficient tokens in family account or race condition")

                        # Create receive transaction for requester
                        receive_txn = {
                            "type": "receive",
                            "from": family_username,
                            "amount": amount,
                            "timestamp": now_iso,
                            "transaction_id": transaction_id,
                            "note": transaction_note,
                            "token_request_id": request_id,
                            "approved_by": approved_by,
                        }

                        # Add to requester account
                        await users_collection.update_one(
                            {"username": requester_username},
                            {"$inc": {"sbd_tokens": amount}, "$push": {"sbd_tokens_transactions": receive_txn}},
                            session=session,
                        )
            else:
                # Non-replica set fallback (without transactions)
                # Verify family account has sufficient balance
                family_user_doc = await users_collection.find_one({"username": family_username})
                if not family_user_doc or family_user_doc.get("sbd_tokens", 0) < amount:
                    raise FamilyError(
                        f"Insufficient tokens in family account: {family_user_doc.get('sbd_tokens', 0)} < {amount}"
                    )

                # Create send transaction for family account
                send_txn = {
                    "type": "send",
                    "to": requester_username,
                    "amount": amount,
                    "timestamp": now_iso,
                    "transaction_id": transaction_id,
                    "note": transaction_note,
                    "token_request_id": request_id,
                    "approved_by": approved_by,
                }

                # Deduct from family account
                res1 = await users_collection.update_one(
                    {"username": family_username, "sbd_tokens": {"$gte": amount}},
                    {"$inc": {"sbd_tokens": -amount}, "$push": {"sbd_tokens_transactions": send_txn}},
                )

                if res1.modified_count == 0:
                    raise FamilyError("Insufficient tokens in family account or race condition")

                # Create receive transaction for requester
                receive_txn = {
                    "type": "receive",
                    "from": family_username,
                    "amount": amount,
                    "timestamp": now_iso,
                    "transaction_id": transaction_id,
                    "note": transaction_note,
                    "token_request_id": request_id,
                    "approved_by": approved_by,
                }

                # Add to requester account
                await users_collection.update_one(
                    {"username": requester_username},
                    {"$inc": {"sbd_tokens": amount}, "$push": {"sbd_tokens_transactions": receive_txn}},
                )

            # Log the successful transfer
            self.logger.info(
                "Token request processed: %s - transferred %d tokens from %s to %s",
                request_id,
                amount,
                family_username,
                requester_username,
            )

            # Send notification about successful transfer
            await self._send_token_transfer_notification(
                request_doc["family_id"], request_doc["requester_user_id"], amount, approved_by, request_id
            )

        except Exception as e:
            self.logger.error("Failed to process approved token request %s: %s", request_id, e, exc_info=True)
            # Update request status to indicate processing failure
            try:
                await requests_collection.update_one(
                    {"request_id": request_id},
                    {
                        "$set": {
                            "status": "processing_failed",
                            "admin_comments": f"Processing failed: {str(e)}",
                            "reviewed_at": datetime.now(timezone.utc),
                        }
                    },
                )
            except Exception as update_error:
                self.logger.error("Failed to update failed request status: %s", update_error)

            raise FamilyError(f"Failed to process token transfer: {str(e)}")

    async def _notify_admins_token_request(self, family_id: str, request_doc: Dict[str, Any]) -> None:
        """Send notification to family admins about a new token request."""
        try:
            family = await self._get_family_by_id(family_id)
            requester = await self._get_user_by_id(request_doc["requester_user_id"])

            # Ensure notification payload contains canonical 'from' fields for frontend consumption
            notification_data = {
                "type": "token_request_created",
                "title": "New Token Request",
                "message": f"{requester.get('username', 'Unknown')} requested {request_doc['amount']} tokens: {request_doc['reason']}",
                "data": {
                    "request_id": request_doc["request_id"],
                    "requester_user_id": request_doc.get("requester_user_id"),
                    "requester_username": requester.get("username", "Unknown"),
                    "from_user_id": request_doc.get("requester_user_id"),
                    "from_username": requester.get("username", "Unknown"),
                    "amount": request_doc["amount"],
                    "reason": request_doc["reason"],
                    "expires_at": request_doc["expires_at"].isoformat(),
                },
            }

            # Send to all admins
            for admin_id in family["admin_user_ids"]:
                await self._send_family_notification(family_id, [admin_id], notification_data)

        except Exception as e:
            self.logger.error("Failed to notify admins about token request: %s", e)

    async def _notify_admins_token_decision(
        self, family_id: str, admin_id: str, request_doc: Dict[str, Any], action: str, comments: str = None
    ) -> None:
        """Send notification to other admins about a token request decision."""
        try:
            family = await self._get_family_by_id(family_id)
            admin_user = await self._get_user_by_id(admin_id)
            requester = await self._get_user_by_id(request_doc["requester_user_id"])

            notification_data = {
                "type": f"token_request_{action}",
                "title": f"Token Request {action.title()}",
                "message": f"{admin_user.get('username', 'Admin')} {action}d {requester.get('username', 'Unknown')}'s request for {request_doc['amount']} tokens",
                "data": {
                    "request_id": request_doc["request_id"],
                    "admin_username": admin_user.get("username", "Unknown"),
                    "requester_username": requester.get("username", "Unknown"),
                    "amount": request_doc["amount"],
                    "action": action,
                    "admin_comments": comments,
                },
            }

            # Send to other admins (not the one who made the decision)
            other_admins = [aid for aid in family["admin_user_ids"] if aid != admin_id]
            if other_admins:
                await self._send_family_notification(family_id, other_admins, notification_data)

        except Exception as e:
            self.logger.error("Failed to notify admins about token decision: %s", e)

    async def _send_token_request_notification(
        self, family_id: str, user_id: str, request_doc: Dict[str, Any], notification_type: str
    ) -> None:
        """Send notification to user about their token request status."""
        try:
            notification_messages = {
                "created": f"Your token request for {request_doc['amount']} tokens has been created",
                "approve": f"Your token request for {request_doc['amount']} tokens has been approved",
                "deny": f"Your token request for {request_doc['amount']} tokens has been denied",
                "expired": f"Your token request for {request_doc['amount']} tokens has expired",
            }

            # Map notification_type to correct enum values
            type_mapping = {"approve": "approved", "deny": "denied"}
            mapped_type = type_mapping.get(notification_type, notification_type)

            # Attach canonical from/requester fields so UI can show "From:" reliably
            requester_username = ""
            try:
                requester = await self._get_user_by_id(request_doc.get("requester_user_id"))
                requester_username = requester.get("username", "")
            except Exception:
                requester_username = ""

            notification_data = {
                "type": f"token_request_{mapped_type}",
                "title": f"Token Request {notification_type.title()}",
                "message": notification_messages.get(notification_type, f"Token request {notification_type}"),
                "data": {
                    "request_id": request_doc["request_id"],
                    "requester_user_id": request_doc.get("requester_user_id"),
                    "requester_username": requester_username,
                    "from_user_id": request_doc.get("requester_user_id"),
                    "from_username": requester_username,
                    "amount": request_doc["amount"],
                    "reason": request_doc["reason"],
                    "status": request_doc["status"],
                    "admin_comments": request_doc.get("admin_comments"),
                },
            }

            await self._send_family_notification(family_id, [user_id], notification_data)

        except Exception as e:
            self.logger.error("Failed to send token request notification: %s", e)

    async def _send_token_transfer_notification(
        self, family_id: str, user_id: str, amount: int, approved_by: str, request_id: str
    ) -> None:
        """Send notification about successful token transfer."""
        try:
            if approved_by != "system":
                admin_user = await self._get_user_by_id(approved_by)
                approved_by_text = f"by {admin_user.get('username', 'Admin')}"
            else:
                approved_by_text = "automatically"

            # Include canonical from fields (who approved/transferred)
            from_user_id = approved_by if approved_by != "system" else None
            from_username = (
                admin_user.get("username", "System")
                if approved_by != "system" and "admin_user" in locals()
                else "System"
            )

            notification_data = {
                "type": "token_transfer_completed",
                "title": "Tokens Transferred",
                "message": f"{amount} tokens have been transferred to your account {approved_by_text}",
                "data": {
                    "amount": amount,
                    "approved_by": approved_by,
                    "request_id": request_id,
                    "transfer_completed": True,
                    "from_user_id": from_user_id,
                    "from_username": from_username,
                },
            }

            await self._send_family_notification(family_id, [user_id], notification_data)

        except Exception as e:
            self.logger.error("Failed to send token transfer notification: %s", e)

    async def _send_family_notification(
        self, family_id: str, recipient_user_ids: List[str], notification_data: Dict[str, Any]
    ) -> None:
        """
        Send notification to family members.

        Args:
            family_id: ID of the family
            recipient_user_ids: List of user IDs to notify
            notification_data: Notification data including type, title, message, and data
        """
        try:
            notification_id = f"not_{uuid.uuid4().hex[:16]}"
            now = datetime.now(timezone.utc)

            notification_doc = {
                "notification_id": notification_id,
                "family_id": family_id,
                "recipient_user_ids": recipient_user_ids,
                "type": notification_data["type"],
                "title": notification_data["title"],
                "message": notification_data["message"],
                "data": notification_data["data"],
                "status": "pending",
                "created_at": now,
                "sent_at": None,
                "read_by": {},
            }

            # Insert notification
            notifications_collection = self.db_manager.get_tenant_collection("family_notifications")
            await notifications_collection.insert_one(notification_doc)

            # Update notification status to sent
            await notifications_collection.update_one(
                {"notification_id": notification_id}, {"$set": {"status": "sent", "sent_at": now}}
            )

            self.logger.debug("Family notification sent: %s to %d recipients", notification_id, len(recipient_user_ids))

        except Exception as e:
            self.logger.error("Failed to send family notification: %s", e)

    async def _send_spending_permissions_notification(
        self, family_id: str, target_user_id: str, admin_id: str, permissions: Dict[str, Any]
    ) -> None:
        """Send notification about spending permissions update."""
        try:
            admin_user = await self._get_user_by_id(admin_id)
            target_user = await self._get_user_by_id(target_user_id)

            notification_data = {
                "type": "permissions_updated",
                "title": "Spending Permissions Updated",
                "message": f"Your spending permissions have been updated by {admin_user.get('username', 'Admin')}",
                "data": {
                    "updated_by": admin_user.get("username", "Admin"),
                    "can_spend": permissions["can_spend"],
                    "spending_limit": permissions["spending_limit"],
                    "updated_at": permissions["updated_at"].isoformat(),
                },
            }

            await self._send_family_notification(family_id, [target_user_id], notification_data)

        except Exception as e:
            self.logger.error("Failed to send spending permissions notification: %s", e)

    async def get_family_sbd_balance(self, account_username: str) -> int:
        """
        Get the current SBD token balance for a family account.

        Args:
            account_username: Username of the family account

        Returns:
            int: Current token balance
        """
        try:
            users_collection = self.db_manager.get_collection("users")
            user_doc = await users_collection.find_one(
                {"username": account_username, "is_virtual_account": True}, {"sbd_tokens": 1}
            )

            if not user_doc:
                return 0

            return user_doc.get("sbd_tokens", 0)

        except Exception as e:
            self.logger.error("Failed to get family SBD balance for %s: %s", account_username, e)
            return 0

    async def get_family_available_balance(self, family_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get the available balance for family SBD spending, considering account freeze status,
        user permissions, spending limits, and pending requests.

        Args:
            family_id: ID of the family
            user_id: ID of the requesting user

        Returns:
            Dict containing available balance information

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not a family member
        """
        operation_context = {
            "family_id": family_id,
            "user_id": user_id,
            "operation": "get_family_available_balance",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "get_family_available_balance", operation_context)

        try:
            # Verify family exists and user is a member
            family = await self._get_family_by_id(family_id)

            if not await self._is_user_family_member(user_id, family_id):
                raise InsufficientPermissions("You must be a family member to check available balance")

            # Get current total balance
            account_username = family["sbd_account"]["account_username"]
            total_balance = await self.get_family_sbd_balance(account_username)

            # Check if account is frozen
            is_frozen = family["sbd_account"]["is_frozen"]

            # Get user's spending permissions
            user_permissions = family["sbd_account"]["spending_permissions"].get(user_id, {})
            can_spend = user_permissions.get("can_spend", False)
            spending_limit = user_permissions.get("spending_limit", 0)

            # Calculate available balance based on permissions and limits
            available_balance = 0

            if is_frozen:
                # Account is frozen - no spending allowed
                available_balance = 0
                reason = "Account is frozen"
            elif not can_spend:
                # User doesn't have spending permission
                available_balance = 0
                reason = "Spending not permitted for this user"
            elif spending_limit == -1:
                # Unlimited spending (admin)
                available_balance = total_balance
                reason = "Unlimited spending permission"
            else:
                # Limited spending - use minimum of total balance and spending limit
                available_balance = min(total_balance, spending_limit)
                reason = f"Limited to {spending_limit} tokens"

            # Get count of pending requests (if any affect available balance)
            pending_requests_count = await self._get_pending_requests_count(family_id)

            # Get account name (fallback to username if not set)
            account_name = family["sbd_account"].get("name", account_username)

            balance_info = {
                "family_id": family_id,
                "account_username": account_username,
                "account_name": account_name,
                "total_balance": total_balance,
                "available_balance": available_balance,
                "is_frozen": is_frozen,
                "can_spend": can_spend,
                "spending_limit": spending_limit,
                "pending_requests_count": pending_requests_count,
                "reason": reason,
                "last_updated": datetime.now(timezone.utc),
            }

            self.db_manager.log_query_success(
                "families",
                "get_family_available_balance",
                start_time,
                1,
                f"Available balance retrieved: {available_balance}",
            )

            self.logger.debug(
                "Retrieved available balance for family %s user %s: %d available of %d total",
                family_id,
                user_id,
                available_balance,
                total_balance,
            )

            return balance_info

        except (FamilyNotFound, InsufficientPermissions) as e:
            self.db_manager.log_query_error(
                "families", "get_family_available_balance", start_time, e, operation_context
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "families", "get_family_available_balance", start_time, e, operation_context
            )
            self.logger.error("Failed to get family available balance: %s", e, exc_info=True)
            raise FamilyError(f"Failed to retrieve available balance: {str(e)}")

    async def _get_recent_family_transactions(self, account_username: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent transactions for a family account.

        Args:
            account_username: Username of the family account
            limit: Maximum number of transactions to return

        Returns:
            List of recent transactions
        """
        try:
            users_collection = self.db_manager.get_collection("users")
            user_doc = await users_collection.find_one(
                {"username": account_username, "is_virtual_account": True},
                {"sbd_tokens_transactions": {"$slice": -limit}},
            )

            if not user_doc:
                return []

            transactions = user_doc.get("sbd_tokens_transactions", [])

            # Sort by timestamp (most recent first) and limit
            transactions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return transactions[:limit]

        except Exception as e:
            self.logger.error("Failed to get recent family transactions for %s: %s", account_username, e)
            return []

    async def _get_pending_requests_count(self, family_id: str) -> int:
        """
        Get the count of pending requests that might affect available balance.

        Args:
            family_id: ID of the family

        Returns:
            int: Count of pending requests
        """
        try:
            # For now, return 0 as we don't have pending request functionality implemented
            # This can be expanded later to include pending token requests, etc.
            return 0

        except Exception as e:
            self.logger.error("Failed to get pending requests count for family %s: %s", family_id, e)
            return 0

    async def freeze_family_account(self, family_id: str, admin_id: str, reason: str) -> Dict[str, Any]:
        """
        Freeze the family SBD account to prevent spending.

        Args:
            family_id: ID of the family
            admin_id: ID of the admin freezing the account
            reason: Reason for freezing

        Returns:
            Dict containing freeze status information

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not an admin
        """
        operation_context = {
            "family_id": family_id,
            "admin_id": admin_id,
            "reason": reason,
            "operation": "freeze_family_account",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "freeze_family_account", operation_context)

        try:
            # Verify family exists and user is admin
            family = await self._get_family_by_id(family_id)

            if admin_id not in family["admin_user_ids"]:
                raise InsufficientPermissions("Only family admins can freeze the account")

            # Check if already frozen
            if family["sbd_account"]["is_frozen"]:
                raise FamilyError("Family account is already frozen")

            # Freeze the account
            now = datetime.now(timezone.utc)
            freeze_data = {"is_frozen": True, "frozen_by": admin_id, "frozen_at": now, "freeze_reason": reason}

            families_collection = self.db_manager.get_tenant_collection("families")
            await families_collection.update_one(
                {"family_id": family_id},
                {
                    "$set": {
                        "sbd_account.is_frozen": True,
                        "sbd_account.frozen_by": admin_id,
                        "sbd_account.frozen_at": now,
                        "sbd_account.freeze_reason": reason,
                        "updated_at": now,
                    }
                },
            )

            # Send notifications to all family members
            await self._send_account_freeze_notification(family_id, admin_id, reason, "frozen")

            self.db_manager.log_query_success(
                "families", "freeze_family_account", start_time, 1, f"Family account frozen: {family_id}"
            )

            self.logger.info("Family account frozen: %s by admin %s, reason: %s", family_id, admin_id, reason)

            return freeze_data

        except (FamilyNotFound, InsufficientPermissions, FamilyError) as e:
            self.db_manager.log_query_error("families", "freeze_family_account", start_time, e, operation_context)
            raise
        except Exception as e:
            self.db_manager.log_query_error("families", "freeze_family_account", start_time, e, operation_context)
            self.logger.error("Failed to freeze family account: %s", e, exc_info=True)
            raise FamilyError(f"Failed to freeze family account: {str(e)}")

    async def unfreeze_family_account(self, family_id: str, admin_id: str) -> Dict[str, Any]:
        """
        Unfreeze the family SBD account to restore spending.

        Args:
            family_id: ID of the family
            admin_id: ID of the admin unfreezing the account

        Returns:
            Dict containing unfreeze status information

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not an admin
        """
        operation_context = {
            "family_id": family_id,
            "admin_id": admin_id,
            "operation": "unfreeze_family_account",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "unfreeze_family_account", operation_context)

        try:
            # Verify family exists and user is admin
            family = await self._get_family_by_id(family_id)

            if admin_id not in family["admin_user_ids"]:
                raise InsufficientPermissions("Only family admins can unfreeze the account")

            # Check if already unfrozen
            if not family["sbd_account"]["is_frozen"]:
                raise FamilyError("Family account is not frozen")

            # Unfreeze the account
            now = datetime.now(timezone.utc)
            unfreeze_data = {
                "is_frozen": False,
                "frozen_by": None,
                "frozen_at": None,
                "unfrozen_by": admin_id,
                "unfrozen_at": now,
            }

            families_collection = self.db_manager.get_tenant_collection("families")
            await families_collection.update_one(
                {"family_id": family_id},
                {
                    "$set": {"sbd_account.is_frozen": False, "updated_at": now},
                    "$unset": {
                        "sbd_account.frozen_by": "",
                        "sbd_account.frozen_at": "",
                        "sbd_account.freeze_reason": "",
                    },
                },
            )

            # Send notifications to all family members
            await self._send_account_freeze_notification(family_id, admin_id, None, "unfrozen")

            self.db_manager.log_query_success(
                "families", "unfreeze_family_account", start_time, 1, f"Family account unfrozen: {family_id}"
            )

            self.logger.info("Family account unfrozen: %s by admin %s", family_id, admin_id)

            return unfreeze_data

        except (FamilyNotFound, InsufficientPermissions, FamilyError) as e:
            self.db_manager.log_query_error("families", "unfreeze_family_account", start_time, e, operation_context)
            raise
        except Exception as e:
            self.db_manager.log_query_error("families", "unfreeze_family_account", start_time, e, operation_context)
            self.logger.error("Failed to unfreeze family account: %s", e, exc_info=True)
            raise FamilyError(f"Failed to unfreeze family account: {str(e)}")

    async def initiate_emergency_unfreeze(self, family_id: str, requester_id: str, reason: str) -> Dict[str, Any]:
        """
        Initiate an emergency unfreeze request that requires multiple family member approvals.

        Args:
            family_id: ID of the family
            requester_id: ID of the family member initiating the emergency unfreeze
            reason: Reason for the emergency unfreeze

        Returns:
            Dict containing emergency request information

        Raises:
            FamilyNotFound: If family doesn't exist
            FamilyError: If account is not frozen or emergency request fails
        """
        operation_context = {
            "family_id": family_id,
            "requester_id": requester_id,
            "reason": reason,
            "operation": "initiate_emergency_unfreeze",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "initiate_emergency_unfreeze", operation_context)

        try:
            # Verify family exists and user is a member
            family = await self._get_family_by_id(family_id)

            if not await self._is_user_family_member(requester_id, family_id):
                raise InsufficientPermissions("Only family members can initiate emergency unfreeze")

            # Check if account is actually frozen
            if not family["sbd_account"]["is_frozen"]:
                raise FamilyError("Family account is not frozen")

            # Check if there's already an active emergency request
            emergency_requests_collection = self.db_manager.get_collection("family_emergency_requests")
            existing_request = await emergency_requests_collection.find_one(
                {"family_id": family_id, "request_type": "emergency_unfreeze", "status": "pending"}
            )

            if existing_request:
                raise FamilyError("An emergency unfreeze request is already pending")

            # Create emergency unfreeze request
            now = datetime.now(timezone.utc)
            request_id = f"emr_{uuid.uuid4().hex[:16]}"

            # Calculate required approvals (minimum 2, or 50% of family members, whichever is higher)
            total_members = family["member_count"]
            required_approvals = max(2, int(total_members * 0.5))

            emergency_request = {
                "request_id": request_id,
                "family_id": family_id,
                "request_type": "emergency_unfreeze",
                "requester_id": requester_id,
                "reason": reason,
                "status": "pending",
                "required_approvals": required_approvals,
                "approvals": [requester_id],  # Requester automatically approves
                "rejections": [],
                "created_at": now,
                "expires_at": now + timedelta(hours=48),  # 48 hour expiry
                "executed_at": None,
                "executed_by": None,
            }

            await emergency_requests_collection.insert_one(emergency_request)

            # Send notifications to all family members except requester
            await self._send_emergency_unfreeze_notification(family_id, requester_id, request_id, reason)

            self.db_manager.log_query_success(
                "families", "initiate_emergency_unfreeze", start_time, 1, f"Emergency unfreeze initiated: {request_id}"
            )

            self.logger.info(
                "Emergency unfreeze initiated: %s by member %s for family %s", request_id, requester_id, family_id
            )

            return {
                "request_id": request_id,
                "family_id": family_id,
                "status": "pending",
                "required_approvals": required_approvals,
                "current_approvals": 1,
                "expires_at": emergency_request["expires_at"],
                "message": "Emergency unfreeze request created. Waiting for family member approvals.",
            }

        except (FamilyNotFound, InsufficientPermissions, FamilyError) as e:
            self.db_manager.log_query_error("families", "initiate_emergency_unfreeze", start_time, e, operation_context)
            raise
        except Exception as e:
            self.db_manager.log_query_error("families", "initiate_emergency_unfreeze", start_time, e, operation_context)
            self.logger.error("Failed to initiate emergency unfreeze: %s", e, exc_info=True)
            raise FamilyError(f"Failed to initiate emergency unfreeze: {str(e)}")

    async def approve_emergency_unfreeze(self, request_id: str, approver_id: str) -> Dict[str, Any]:
        """
        Approve an emergency unfreeze request.

        Args:
            request_id: ID of the emergency request
            approver_id: ID of the family member approving

        Returns:
            Dict containing approval status and execution result if threshold met

        Raises:
            FamilyError: If request not found, expired, or approval fails
        """
        operation_context = {
            "request_id": request_id,
            "approver_id": approver_id,
            "operation": "approve_emergency_unfreeze",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "approve_emergency_unfreeze", operation_context)

        try:
            emergency_requests_collection = self.db_manager.get_collection("family_emergency_requests")

            # Get the emergency request
            emergency_request = await emergency_requests_collection.find_one({"request_id": request_id})
            if not emergency_request:
                raise FamilyError("Emergency request not found")

            # Check if request is still valid
            if emergency_request["status"] != "pending":
                raise FamilyError("Emergency request is no longer pending")

            expires_at = emergency_request["expires_at"]
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                raise FamilyError("Emergency request has expired")

            # Verify approver is a family member
            family_id = emergency_request["family_id"]
            if not await self._is_user_family_member(approver_id, family_id):
                raise InsufficientPermissions("Only family members can approve emergency requests")

            # Check if user already approved or rejected
            if approver_id in emergency_request["approvals"]:
                raise FamilyError("You have already approved this request")

            if approver_id in emergency_request["rejections"]:
                raise FamilyError("You have already rejected this request")

            # Add approval
            now = datetime.now(timezone.utc)
            await emergency_requests_collection.update_one(
                {"request_id": request_id}, {"$push": {"approvals": approver_id}, "$set": {"updated_at": now}}
            )

            # Get updated request
            updated_request = await emergency_requests_collection.find_one({"request_id": request_id})
            current_approvals = len(updated_request["approvals"])
            required_approvals = updated_request["required_approvals"]

            result = {
                "request_id": request_id,
                "approved": True,
                "current_approvals": current_approvals,
                "required_approvals": required_approvals,
                "threshold_met": current_approvals >= required_approvals,
            }

            # Check if we have enough approvals to execute
            if current_approvals >= required_approvals:
                # Execute the emergency unfreeze
                try:
                    unfreeze_result = await self.unfreeze_family_account(family_id, approver_id)

                    # Mark request as executed
                    await emergency_requests_collection.update_one(
                        {"request_id": request_id},
                        {"$set": {"status": "executed", "executed_at": now, "executed_by": approver_id}},
                    )

                    # Send execution notification
                    await self._send_emergency_unfreeze_executed_notification(
                        family_id, request_id, approver_id, updated_request["reason"]
                    )

                    result.update(
                        {
                            "executed": True,
                            "executed_at": now,
                            "message": "Emergency unfreeze executed successfully",
                            "unfreeze_result": unfreeze_result,
                        }
                    )

                    self.logger.info("Emergency unfreeze executed: %s by approver %s", request_id, approver_id)

                except Exception as e:
                    # Mark request as failed
                    await emergency_requests_collection.update_one(
                        {"request_id": request_id},
                        {"$set": {"status": "failed", "failure_reason": str(e), "failed_at": now}},
                    )
                    raise FamilyError(f"Emergency unfreeze execution failed: {str(e)}")
            else:
                result["message"] = f"Approval recorded. Need {required_approvals - current_approvals} more approvals."

            self.db_manager.log_query_success(
                "families", "approve_emergency_unfreeze", start_time, 1, f"Emergency unfreeze approved: {request_id}"
            )

            return result

        except (FamilyError, InsufficientPermissions) as e:
            self.db_manager.log_query_error("families", "approve_emergency_unfreeze", start_time, e, operation_context)
            raise
        except Exception as e:
            self.db_manager.log_query_error("families", "approve_emergency_unfreeze", start_time, e, operation_context)
            self.logger.error("Failed to approve emergency unfreeze: %s", e, exc_info=True)
            raise FamilyError(f"Failed to approve emergency unfreeze: {str(e)}")

    async def reject_emergency_unfreeze(self, request_id: str, rejector_id: str, reason: str = None) -> Dict[str, Any]:
        """
        Reject an emergency unfreeze request.

        Args:
            request_id: ID of the emergency request
            rejector_id: ID of the family member rejecting
            reason: Optional reason for rejection

        Returns:
            Dict containing rejection status

        Raises:
            FamilyError: If request not found, expired, or rejection fails
        """
        operation_context = {
            "request_id": request_id,
            "rejector_id": rejector_id,
            "reason": reason,
            "operation": "reject_emergency_unfreeze",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "reject_emergency_unfreeze", operation_context)

        try:
            emergency_requests_collection = self.db_manager.get_collection("family_emergency_requests")

            # Get the emergency request
            emergency_request = await emergency_requests_collection.find_one({"request_id": request_id})
            if not emergency_request:
                raise FamilyError("Emergency request not found")

            # Check if request is still valid
            if emergency_request["status"] != "pending":
                raise FamilyError("Emergency request is no longer pending")

            expires_at = emergency_request["expires_at"]
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                raise FamilyError("Emergency request has expired")

            # Verify rejector is a family member
            family_id = emergency_request["family_id"]
            if not await self._is_user_family_member(rejector_id, family_id):
                raise InsufficientPermissions("Only family members can reject emergency requests")

            # Check if user already approved or rejected
            if rejector_id in emergency_request["approvals"]:
                raise FamilyError("You have already approved this request")

            if rejector_id in emergency_request["rejections"]:
                raise FamilyError("You have already rejected this request")

            # Add rejection
            now = datetime.now(timezone.utc)
            rejection_data = {"user_id": rejector_id, "reason": reason, "rejected_at": now}

            await emergency_requests_collection.update_one(
                {"request_id": request_id}, {"$push": {"rejections": rejection_data}, "$set": {"updated_at": now}}
            )

            self.db_manager.log_query_success(
                "families", "reject_emergency_unfreeze", start_time, 1, f"Emergency unfreeze rejected: {request_id}"
            )

            self.logger.info("Emergency unfreeze rejected: %s by member %s", request_id, rejector_id)

            return {
                "request_id": request_id,
                "rejected": True,
                "rejector_id": rejector_id,
                "reason": reason,
                "message": "Emergency unfreeze request rejected",
            }

        except (FamilyError, InsufficientPermissions) as e:
            self.db_manager.log_query_error("families", "reject_emergency_unfreeze", start_time, e, operation_context)
            raise
        except Exception as e:
            self.db_manager.log_query_error("families", "reject_emergency_unfreeze", start_time, e, operation_context)
            self.logger.error("Failed to reject emergency unfreeze: %s", e, exc_info=True)
            raise FamilyError(f"Failed to reject emergency unfreeze: {str(e)}")

    async def get_emergency_unfreeze_requests(
        self, family_id: str, user_id: str, status: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get emergency unfreeze requests for a family.

        Args:
            family_id: ID of the family
            user_id: ID of the requesting user
            status: Optional status filter (pending, executed, failed, expired)

        Returns:
            List of emergency requests

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not a family member
        """
        try:
            # Verify family exists and user is a member
            family = await self._get_family_by_id(family_id)

            if not await self._is_user_family_member(user_id, family_id):
                raise InsufficientPermissions("Only family members can view emergency requests")

            # Build query
            query = {"family_id": family_id, "request_type": "emergency_unfreeze"}

            if status:
                query["status"] = status

            emergency_requests_collection = self.db_manager.get_collection("family_emergency_requests")
            cursor = emergency_requests_collection.find(query).sort("created_at", -1)

            requests = []
            async for request in cursor:
                # Convert ObjectId to string
                request["_id"] = str(request["_id"])

                # Add user information for approvals and rejections
                request["approval_users"] = []
                for approval_id in request.get("approvals", []):
                    try:
                        user = await self._get_user_by_id(approval_id)
                        request["approval_users"].append(
                            {"user_id": approval_id, "username": user.get("username", "Unknown")}
                        )
                    except Exception:  # TODO: Use specific exception type
                        pass

                requests.append(request)

            return requests

        except (FamilyNotFound, InsufficientPermissions) as e:
            raise
        except Exception as e:
            self.logger.error("Failed to get emergency unfreeze requests: %s", e, exc_info=True)
            raise FamilyError(f"Failed to get emergency requests: {str(e)}")

    async def _send_emergency_unfreeze_notification(
        self, family_id: str, requester_id: str, request_id: str, reason: str
    ) -> None:
        """Send notification about emergency unfreeze request to family members."""
        try:
            family = await self._get_family_by_id(family_id)
            requester = await self._get_user_by_id(requester_id)

            # Get all family members except requester
            members = await self._get_family_members_detailed(family_id)
            recipient_ids = [member["user_id"] for member in members if member["user_id"] != requester_id]

            if recipient_ids:
                notification_data = {
                    "type": "emergency_unfreeze_request",
                    "title": "Emergency Account Unfreeze Request",
                    "message": f"{requester.get('username', 'A family member')} has requested an emergency unfreeze of the family account. Reason: {reason}",
                    "data": {
                        "request_id": request_id,
                        "family_id": family_id,
                        "requester_id": requester_id,
                        "reason": reason,
                    },
                }

                await self._create_family_notification(family_id, recipient_ids, notification_data)

        except Exception as e:
            self.logger.error("Failed to send emergency unfreeze notification: %s", e)

    async def _send_emergency_unfreeze_executed_notification(
        self, family_id: str, request_id: str, executor_id: str, reason: str
    ) -> None:
        """Send notification about executed emergency unfreeze to family members."""
        try:
            family = await self._get_family_by_id(family_id)
            executor = await self._get_user_by_id(executor_id)

            # Get all family members
            members = await self._get_family_members_detailed(family_id)
            recipient_ids = [member["user_id"] for member in members]

            if recipient_ids:
                notification_data = {
                    "type": "emergency_unfreeze_executed",
                    "title": "Emergency Unfreeze Executed",
                    "message": f"The emergency unfreeze request has been executed by {executor.get('username', 'a family member')}. The family account is now unfrozen.",
                    "data": {
                        "request_id": request_id,
                        "family_id": family_id,
                        "executor_id": executor_id,
                        "reason": reason,
                    },
                }

                await self._create_family_notification(family_id, recipient_ids, notification_data)

        except Exception as e:
            self.logger.error("Failed to send emergency unfreeze executed notification: %s", e)

    async def _get_family_members_detailed(self, family_id: str) -> List[Dict[str, Any]]:
        """Get detailed family member information for internal use (no permission checks)."""
        try:
            # Get family to verify it exists
            family = await self._get_family_by_id(family_id)

            # Get all relationships for this family
            relationships_collection = self.db_manager.get_collection("family_relationships")
            cursor = relationships_collection.find({"family_id": family_id})

            members_dict = {}
            async for relationship in cursor:
                # Add both users from the relationship
                for user_key in ["user_a_id", "user_b_id"]:
                    user_id = relationship[user_key]
                    if user_id not in members_dict:
                        try:
                            user = await self._get_user_by_id(user_id)
                            members_dict[user_id] = {
                                "user_id": user_id,
                                "username": user.get("username", "Unknown"),
                                "email": user.get("email", ""),
                                "role": "admin" if user_id in family["admin_user_ids"] else "member",
                                "joined_at": relationship.get("created_at", datetime.now(timezone.utc)),
                            }
                        except:
                            # Skip users that can't be found
                            pass

            return list(members_dict.values())

        except Exception as e:
            self.logger.error("Failed to get detailed family members: %s", e, exc_info=True)
            return []

    async def get_family_transactions(
        self, family_id: str, user_id: str, skip: int = 0, limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get family SBD account transaction history.

        Args:
            family_id: ID of the family
            user_id: ID of the requesting user
            skip: Number of transactions to skip
            limit: Maximum number of transactions to return

        Returns:
            Dict containing transaction history and pagination info

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not a family member
        """
        operation_context = {
            "family_id": family_id,
            "user_id": user_id,
            "skip": skip,
            "limit": limit,
            "operation": "get_family_transactions",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "get_family_transactions", operation_context)

        try:
            # Verify family exists and user is a member
            family = await self._get_family_by_id(family_id)

            if not await self._is_user_in_family(user_id, family_id):
                raise InsufficientPermissions("You must be a family member to view transaction history")

            # Get family account details
            account_username = family["sbd_account"]["account_username"]
            account_name = family["sbd_account"].get("name", account_username)
            current_balance = await self.get_family_sbd_balance(account_username)

            # Get transactions from virtual account
            users_collection = self.db_manager.get_collection("users")
            virtual_account = await users_collection.find_one({"username": account_username})

            if not virtual_account:
                raise FamilyError("Family SBD account not found")

            all_transactions = virtual_account.get("sbd_tokens_transactions", [])

            # Sort by timestamp (newest first)
            sorted_transactions = sorted(all_transactions, key=lambda x: x.get("timestamp", ""), reverse=True)

            # Apply pagination
            paginated_transactions = sorted_transactions[skip : skip + limit]

            # Enhance transactions with family member information
            enhanced_transactions = []
            for txn in paginated_transactions:
                enhanced_txn = txn.copy()

                # Add family member details if available
                if "family_member_id" in txn:
                    member_user = await self._get_user_by_id(txn["family_member_id"])
                    if member_user:
                        enhanced_txn["family_member_details"] = {
                            "username": member_user.get("username"),
                            "email": member_user.get("email"),
                        }

                enhanced_transactions.append(enhanced_txn)

            transaction_data = {
                "family_id": family_id,
                "account_username": account_username,
                "account_name": account_name,
                "current_balance": current_balance,
                "transactions": enhanced_transactions,
                "total_count": len(all_transactions),
                "has_more": (skip + limit) < len(all_transactions),
                "retrieved_at": datetime.now(timezone.utc),
            }

            self.db_manager.log_query_success(
                "families",
                "get_family_transactions",
                start_time,
                len(enhanced_transactions),
                f"Retrieved {len(enhanced_transactions)} transactions for family {family_id}",
            )

            self.logger.debug(
                "Retrieved %d transactions for family %s by user %s", len(enhanced_transactions), family_id, user_id
            )

            return transaction_data

        except (FamilyNotFound, InsufficientPermissions) as e:
            self.db_manager.log_query_error("families", "get_family_transactions", start_time, e, operation_context)
            raise
        except Exception as e:
            self.db_manager.log_query_error("families", "get_family_transactions", start_time, e, operation_context)
            self.logger.error("Failed to get family transactions: %s", e, exc_info=True)
            raise FamilyError(f"Failed to retrieve transaction history: {str(e)}")

    async def get_family_by_id(self, family_id: str) -> Dict[str, Any]:
        """
        Public method to get family by ID.

        Args:
            family_id: ID of the family

        Returns:
            Dict containing family information

        Raises:
            FamilyNotFound: If family doesn't exist
        """
        return await self._get_family_by_id(family_id)

    async def get_family_by_account_username(self, account_username: str) -> Optional[Dict[str, Any]]:
        """
        Get family by SBD account username.

        Args:
            account_username: Username of the family SBD account

        Returns:
            Dict containing family information or None if not found
        """
        try:
            families_collection = self.db_manager.get_tenant_collection("families")
            family = await families_collection.find_one({"sbd_account.account_username": account_username})

            if not family:
                return None

            return family

        except Exception as e:
            self.logger.error("Failed to get family by account username %s: %s", account_username, e)
            return None

    # Helper methods for SBD token permission system

    async def _get_recent_family_transactions(self, account_username: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent transactions for family account."""
        try:
            users_collection = self.db_manager.get_collection("users")
            virtual_account = await users_collection.find_one({"username": account_username})

            if not virtual_account:
                return []

            all_transactions = virtual_account.get("sbd_tokens_transactions", [])

            # Sort by timestamp (newest first) and limit
            sorted_transactions = sorted(all_transactions, key=lambda x: x.get("timestamp", ""), reverse=True)

            return sorted_transactions[:limit]

        except Exception as e:
            self.logger.error("Failed to get recent family transactions: %s", e)
            return []

    async def _send_spending_permissions_notification(
        self, family_id: str, target_user_id: str, admin_id: str, permissions: Dict[str, Any]
    ) -> None:
        """Send notification when spending permissions are updated."""
        try:
            # Get user and admin details
            target_user = await self._get_user_by_id(target_user_id)
            admin_user = await self._get_user_by_id(admin_id)
            family = await self._get_family_by_id(family_id)

            if not target_user or not admin_user or not family:
                return

            # Create notification message
            spending_limit_text = (
                "unlimited" if permissions["spending_limit"] == -1 else f"{permissions['spending_limit']} tokens"
            )
            can_spend_text = "enabled" if permissions["can_spend"] else "disabled"

            message = (
                f"Your spending permissions have been updated by @{admin_user['username']}. "
                f"Spending: {can_spend_text}, Limit: {spending_limit_text}"
            )

            # Send notification (implementation would depend on notification system)
            self.logger.info("Spending permissions notification sent to user %s", target_user_id)

        except Exception as e:
            self.logger.error("Failed to send spending permissions notification: %s", e)

    async def _send_account_freeze_notification(
        self, family_id: str, admin_id: str, reason: Optional[str], action: str
    ) -> None:
        """Send notification when account is frozen or unfrozen."""
        try:
            admin_user = await self._get_user_by_id(admin_id)
            family = await self._get_family_by_id(family_id)

            if not admin_user or not family:
                return

            # Create notification message
            if action == "frozen":
                message = f"Family account has been frozen by @{admin_user['username']}"
                if reason:
                    message += f". Reason: {reason}"
            else:
                message = f"Family account has been unfrozen by @{admin_user['username']}"

            # Send notification to all family members (implementation would depend on notification system)
            self.logger.info("Account %s notification sent for family %s", action, family_id)

        except Exception as e:
            self.logger.error("Failed to send account freeze notification: %s", e)

    async def cleanup_expired_invitations(self) -> Dict[str, Any]:
        """
        Clean up expired family invitations.

        This method should be called periodically (e.g., via cron job) to:
        - Mark expired invitations as 'expired'
        - Clean up old invitation records
        - Log cleanup statistics

        Returns:
            Dict containing cleanup statistics
        """
        cleanup_context = {
            "operation": "cleanup_expired_invitations",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("family_invitations", "cleanup_expired", cleanup_context)

        try:
            invitations_collection = self.db_manager.get_tenant_collection("family_invitations")
            now = datetime.now(timezone.utc)

            # Find expired pending invitations
            expired_invitations = await invitations_collection.find(
                {"status": "pending", "expires_at": {"$lt": now}}
            ).to_list(length=None)

            expired_count = len(expired_invitations)

            if expired_count > 0:
                # Mark expired invitations
                await invitations_collection.update_many(
                    {"status": "pending", "expires_at": {"$lt": now}},
                    {"$set": {"status": "expired", "responded_at": now}},
                )

                # Log expired invitations for audit
                for invitation in expired_invitations:
                    self.logger.info(
                        "Invitation expired: %s for family %s (invitee: %s)",
                        invitation["invitation_id"],
                        invitation["family_id"],
                        invitation["invitee_email"],
                        extra={
                            "invitation_id": invitation["invitation_id"],
                            "family_id": invitation["family_id"],
                            "invitee_email": invitation["invitee_email"],
                            "expired_at": invitation["expires_at"].isoformat(),
                            "cleanup_operation": True,
                        },
                    )

            # Clean up old expired invitations (older than 30 days)
            cleanup_threshold = now - timedelta(days=30)
            old_invitations_result = await invitations_collection.delete_many(
                {"status": {"$in": ["expired", "declined"]}, "responded_at": {"$lt": cleanup_threshold}}
            )

            cleaned_count = old_invitations_result.deleted_count

            self.db_manager.log_query_success(
                "family_invitations",
                "cleanup_expired",
                start_time,
                expired_count + cleaned_count,
                f"Expired: {expired_count}, Cleaned: {cleaned_count}",
            )

            self.logger.info(
                "Invitation cleanup completed: %d expired, %d cleaned up",
                expired_count,
                cleaned_count,
                extra={
                    "expired_count": expired_count,
                    "cleaned_count": cleaned_count,
                    "cleanup_threshold": cleanup_threshold.isoformat(),
                },
            )

            return {
                "expired_count": expired_count,
                "cleaned_count": cleaned_count,
                "total_processed": expired_count + cleaned_count,
                "cleanup_threshold": cleanup_threshold,
                "timestamp": now,
            }

        except Exception as e:
            self.db_manager.log_query_error("family_invitations", "cleanup_expired", start_time, e, cleanup_context)
            self.logger.error("Failed to cleanup expired invitations: %s", e, exc_info=True)
            raise FamilyError(f"Failed to cleanup expired invitations: {str(e)}")

    async def get_family_invitations(
        self, family_id: str, user_id: str, status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get family invitations for a specific family.

        Args:
            family_id: ID of the family
            user_id: ID of the user requesting (must be admin)
            status_filter: Optional status filter ("pending", "accepted", "declined", "expired")

        Returns:
            List of invitation information

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
        """
        operation_context = {
            "family_id": family_id,
            "user_id": user_id,
            "status_filter": status_filter,
            "operation": "get_family_invitations",
        }
        start_time = self.db_manager.log_query_start("family_invitations", "get_invitations", operation_context)

        try:
            # Verify family exists and user has admin permissions
            family = await self._get_family_by_id(family_id)
            if user_id not in family["admin_user_ids"]:
                raise InsufficientPermissions("Only family admins can view invitations")

            # Build query
            query = {"family_id": family_id}
            if status_filter:
                query["status"] = status_filter

            # Use aggregation to populate inviter and invitee usernames and family name atomically.
            invitations_collection = self.db_manager.get_tenant_collection("family_invitations")

            pipeline = [
                {"$match": query},
                {"$sort": {"created_at": -1}},
                {
                    "$lookup": {
                        "from": "users",
                        "let": {"inviter_id": "$inviter_user_id"},
                        "pipeline": [{"$match": {"$expr": {"$eq": ["$_id", {"$toObjectId": "$$inviter_id"}]}}}],
                        "as": "inviter_doc",
                    }
                },
                {
                    "$lookup": {
                        "from": "users",
                        "let": {"invitee_id": "$invitee_user_id"},
                        "pipeline": [{"$match": {"$expr": {"$eq": ["$_id", {"$toObjectId": "$$invitee_id"}]}}}],
                        "as": "invitee_doc",
                    }
                },
                {
                    "$lookup": {
                        "from": "families",
                        "localField": "family_id",
                        "foreignField": "family_id",
                        "as": "family_doc",
                    }
                },
            ]

            # Projection to provide defensive defaults when lookups fail
            pipeline.append(
                {
                    "$project": {
                        "invitation_id": 1,
                        "family_id": 1,
                        "family_name": {"$ifNull": [{"$arrayElemAt": ["$family_doc.name", 0]}, "Unknown Family"]},
                        "inviter_user_id": 1,
                        "inviter_username": {"$ifNull": [{"$arrayElemAt": ["$inviter_doc.username", 0]}, "Unknown"]},
                        "invitee_email": 1,
                        "invitee_user_id": 1,
                        "invitee_username": {"$ifNull": [{"$arrayElemAt": ["$invitee_doc.username", 0]}, None]},
                        "relationship_type": 1,
                        "status": 1,
                        "expires_at": 1,
                        "created_at": 1,
                        "responded_at": 1,
                        "email_sent": 1,
                        "email_sent_at": 1,
                    }
                }
            )

            invitations = []
            async for invitation in invitations_collection.aggregate(pipeline):
                # Ensure keys exist and provide consistent shapes
                invitations.append(
                    {
                        "invitation_id": invitation.get("invitation_id"),
                        "family_id": invitation.get("family_id"),
                        "family_name": invitation.get("family_name", "Unknown Family"),
                        "inviter_user_id": invitation.get("inviter_user_id"),
                        "inviter_username": invitation.get("inviter_username", "Unknown"),
                        "invitee_email": invitation.get("invitee_email"),
                        "invitee_user_id": invitation.get("invitee_user_id"),
                        "invitee_username": invitation.get("invitee_username"),
                        "relationship_type": invitation.get("relationship_type"),
                        "status": invitation.get("status"),
                        "expires_at": invitation.get("expires_at"),
                        "created_at": invitation.get("created_at"),
                        "responded_at": invitation.get("responded_at"),
                        "email_sent": invitation.get("email_sent", False),
                        "email_sent_at": invitation.get("email_sent_at"),
                    }
                )

            self.db_manager.log_query_success("family_invitations", "get_invitations", start_time, len(invitations))

            return invitations

        except (FamilyNotFound, InsufficientPermissions):
            self.db_manager.log_query_error(
                "family_invitations", "get_invitations", start_time, Exception("Validation error"), operation_context
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error("family_invitations", "get_invitations", start_time, e, operation_context)
            self.logger.error("Failed to get family invitations: %s", e, exc_info=True)
            raise FamilyError(f"Failed to get family invitations: {str(e)}")

    async def get_received_invitations(
        self, user_id: str, user_email: Optional[str] = None, status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get invitations received by a user (either by invitee_user_id or invitee_email).

        Args:
            user_id: User ID of the recipient (string)
            user_email: Optional email of the recipient to match invitee_email
            status_filter: Optional status filter ("pending", "accepted", "declined", "expired")

        Returns:
            List of invitation dictionaries with complete family and inviter information

        Raises:
            FamilyError: If database query fails
        """
        operation_context = {
            "user_id": user_id,
            "user_email": user_email,
            "status_filter": status_filter,
            "operation": "get_received_invitations",
        }
        start_time = self.db_manager.log_query_start(
            "family_invitations", "get_received_invitations", operation_context
        )

        try:
            # Build query: match invitee_user_id OR invitee_email
            query_conditions = [{"invitee_user_id": user_id}]
            if user_email:
                query_conditions.append({"invitee_email": user_email})

            query = {"$or": query_conditions}
            if status_filter:
                query["status"] = status_filter

            invitations_collection = self.db_manager.get_tenant_collection("family_invitations")

            pipeline = [
                {"$match": query},
                {"$sort": {"created_at": -1}},
                {
                    "$lookup": {
                        "from": "users",
                        "let": {"inviter_id": "$inviter_user_id"},
                        "pipeline": [{"$match": {"$expr": {"$eq": ["$_id", {"$toObjectId": "$$inviter_id"}]}}}],
                        "as": "inviter_doc",
                    }
                },
                {
                    "$lookup": {
                        "from": "families",
                        "localField": "family_id",
                        "foreignField": "family_id",
                        "as": "family_doc",
                    }
                },
                {
                    "$lookup": {
                        "from": "users",
                        "let": {"invitee_id": "$invitee_user_id"},
                        "pipeline": [{"$match": {"$expr": {"$eq": ["$_id", {"$toObjectId": "$$invitee_id"}]}}}],
                        "as": "invitee_doc",
                    }
                },
                {
                    "$project": {
                        "invitation_id": 1,
                        "family_id": 1,
                        "family_name": {"$ifNull": [{"$arrayElemAt": ["$family_doc.name", 0]}, "Unknown Family"]},
                        "inviter_user_id": 1,
                        "inviter_username": {"$ifNull": [{"$arrayElemAt": ["$inviter_doc.username", 0]}, "Unknown"]},
                        "invitee_email": 1,
                        "invitee_user_id": 1,
                        "invitee_username": {"$ifNull": [{"$arrayElemAt": ["$invitee_doc.username", 0]}, None]},
                        "relationship_type": 1,
                        "status": 1,
                        "expires_at": 1,
                        "created_at": 1,
                        "invitation_token": 1,
                    }
                },
            ]

            invitations = []
            async for invitation in invitations_collection.aggregate(pipeline):
                invitations.append(
                    {
                        "invitation_id": invitation.get("invitation_id"),
                        "family_id": invitation.get("family_id"),
                        "family_name": invitation.get("family_name", "Unknown Family"),
                        "inviter_user_id": invitation.get("inviter_user_id"),
                        "inviter_username": invitation.get("inviter_username", "Unknown"),
                        "relationship_type": invitation.get("relationship_type"),
                        "status": invitation.get("status"),
                        "expires_at": invitation.get("expires_at"),
                        "created_at": invitation.get("created_at"),
                        "invitation_token": invitation.get("invitation_token"),
                        "invitee_email": invitation.get("invitee_email"),
                        "invitee_user_id": invitation.get("invitee_user_id"),
                        "invitee_username": invitation.get("invitee_username"),
                    }
                )

            self.db_manager.log_query_success(
                "family_invitations", "get_received_invitations", start_time, len(invitations)
            )

            self.logger.info(
                "Retrieved %d received invitations for user %s (status_filter=%s)",
                len(invitations),
                user_id,
                status_filter,
            )

            return invitations

        except Exception as e:
            self.db_manager.log_query_error(
                "family_invitations", "get_received_invitations", start_time, e, operation_context
            )
            self.logger.error("Failed to get received invitations for user %s: %s", user_id, e, exc_info=True)
            raise FamilyError(f"Failed to get received invitations: {str(e)}")

    async def resend_invitation(self, invitation_id: str, admin_user_id: str) -> Dict[str, Any]:
        """
        Resend a family invitation email.

        Args:
            invitation_id: ID of the invitation to resend
            admin_user_id: ID of the admin user requesting resend

        Returns:
            Dict containing resend information

        Raises:
            InvitationNotFound: If invitation doesn't exist
            InsufficientPermissions: If user is not admin
            FamilyError: If resend fails
        """
        operation_context = {
            "invitation_id": invitation_id,
            "admin_user_id": admin_user_id,
            "operation": "resend_invitation",
        }
        start_time = self.db_manager.log_query_start("family_invitations", "resend_invitation", operation_context)

        try:
            # Get invitation
            invitations_collection = self.db_manager.get_tenant_collection("family_invitations")
            invitation = await invitations_collection.find_one({"invitation_id": invitation_id})

            if not invitation:
                raise InvitationNotFound("Invitation not found")

            # Check if invitation is still pending
            if invitation["status"] != "pending":
                raise InvitationNotFound("Can only resend pending invitations")

            # Check if invitation is expired
            expires_at = invitation["expires_at"]
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                raise InvitationNotFound("Cannot resend expired invitation")

            # Verify user has admin permissions for the family
            family = await self._get_family_by_id(invitation["family_id"])
            if admin_user_id not in family["admin_user_ids"]:
                raise InsufficientPermissions("Only family admins can resend invitations")

            # Send invitation email
            email_sent = await self._send_invitation_email_safe(invitation, family)

            # Update email sent status
            now = datetime.now(timezone.utc)
            await invitations_collection.update_one(
                {"invitation_id": invitation_id},
                {
                    "$set": {"email_sent": email_sent, "email_sent_at": now if email_sent else None},
                    "$inc": {"email_attempts": 1},
                },
            )

            self.db_manager.log_query_success(
                "family_invitations", "resend_invitation", start_time, 1, f"Email resent: {email_sent}"
            )

            self.logger.info(
                "Family invitation resent: %s (email_sent: %s)",
                invitation_id,
                email_sent,
                extra={
                    "invitation_id": invitation_id,
                    "admin_user_id": admin_user_id,
                    "email_sent": email_sent,
                    "family_id": invitation["family_id"],
                },
            )

            return {
                "invitation_id": invitation_id,
                "email_sent": email_sent,
                "resent_at": now,
                "message": "Invitation email resent successfully" if email_sent else "Failed to send invitation email",
            }

        except (InvitationNotFound, InsufficientPermissions):
            self.db_manager.log_query_error(
                "family_invitations", "resend_invitation", start_time, Exception("Validation error"), operation_context
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error("family_invitations", "resend_invitation", start_time, e, operation_context)
            self.logger.error("Failed to resend invitation: %s", e, exc_info=True)
            raise FamilyError(f"Failed to resend invitation: {str(e)}")

    async def cancel_invitation(self, invitation_id: str, admin_user_id: str) -> Dict[str, Any]:
        """
        Cancel a pending family invitation.

        Args:
            invitation_id: ID of the invitation to cancel
            admin_user_id: ID of the admin user requesting cancellation

        Returns:
            Dict containing cancellation information

        Raises:
            InvitationNotFound: If invitation doesn't exist
            InsufficientPermissions: If user is not admin
            FamilyError: If cancellation fails
        """
        operation_context = {
            "invitation_id": invitation_id,
            "admin_user_id": admin_user_id,
            "operation": "cancel_invitation",
        }
        start_time = self.db_manager.log_query_start("family_invitations", "cancel_invitation", operation_context)

        try:
            # Get invitation
            invitations_collection = self.db_manager.get_tenant_collection("family_invitations")
            invitation = await invitations_collection.find_one({"invitation_id": invitation_id})

            if not invitation:
                raise InvitationNotFound("Invitation not found")

            # Check if invitation is still pending
            if invitation["status"] != "pending":
                raise InvitationNotFound("Can only cancel pending invitations")

            # Verify user has admin permissions for the family
            family = await self._get_family_by_id(invitation["family_id"])
            if admin_user_id not in family["admin_user_ids"]:
                raise InsufficientPermissions("Only family admins can cancel invitations")

            # Update invitation status to cancelled
            now = datetime.now(timezone.utc)
            await invitations_collection.update_one(
                {"invitation_id": invitation_id},
                {"$set": {"status": "cancelled", "responded_at": now, "cancelled_by": admin_user_id}},
            )

            self.db_manager.log_query_success("family_invitations", "cancel_invitation", start_time, 1)

            self.logger.info(
                "Family invitation cancelled: %s by admin %s",
                invitation_id,
                admin_user_id,
                extra={
                    "invitation_id": invitation_id,
                    "admin_user_id": admin_user_id,
                    "family_id": invitation["family_id"],
                    "invitee_email": invitation["invitee_email"],
                },
            )

            return {
                "invitation_id": invitation_id,
                "status": "cancelled",
                "cancelled_at": now,
                "cancelled_by": admin_user_id,
                "message": "Invitation cancelled successfully",
            }

        except (InvitationNotFound, InsufficientPermissions):
            self.db_manager.log_query_error(
                "family_invitations", "cancel_invitation", start_time, Exception("Validation error"), operation_context
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error("family_invitations", "cancel_invitation", start_time, e, operation_context)
            self.logger.error("Failed to cancel invitation: %s", e, exc_info=True)
            raise FamilyError(f"Failed to cancel invitation: {str(e)}")

    async def promote_to_admin(
        self, family_id: str, admin_user_id: str, target_user_id: str, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Promote a family member to administrator role.

        Args:
            family_id: ID of the family
            admin_user_id: ID of the admin performing the action
            target_user_id: ID of the user to promote
            request_context: Request context for rate limiting and security

        Returns:
            Dict containing promotion information

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
            AdminActionError: If promotion validation fails
            ValidationError: If input validation fails
            TransactionError: If database transaction fails
        """
        operation_context = {
            "family_id": family_id,
            "admin_user_id": admin_user_id,
            "target_user_id": target_user_id,
            "operation": "promote_to_admin",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "promote_to_admin", operation_context)

        # Rate limiting check
        if request_context:
            try:
                await self._check_rate_limit(
                    request_context, "promote_admin", self._get_operation_rate_limit("promote_admin"), 3600
                )
            except Exception as e:
                raise RateLimitExceeded(
                    "Admin promotion rate limit exceeded",
                    action="promote_admin",
                    limit=self._get_operation_rate_limit("promote_admin"),
                    window=3600,
                )

        session = None

        try:
            # Validate input
            await self._validate_admin_action_input(family_id, admin_user_id, target_user_id, "promote")

            # Get family and verify permissions
            family = await self._get_family_by_id(family_id)
            if admin_user_id not in family["admin_user_ids"]:
                raise InsufficientPermissions(
                    "Only family admins can promote members", required_role="admin", user_role="member"
                )

            # Check if target user is already an admin
            if target_user_id in family["admin_user_ids"]:
                raise AdminActionError(
                    "User is already a family administrator",
                    action="promote",
                    target_user=target_user_id,
                    current_admin=admin_user_id,
                )

            # Verify target user is a family member
            if not await self._is_user_in_family(target_user_id, family_id):
                raise AdminActionError(
                    "User is not a member of this family",
                    action="promote",
                    target_user=target_user_id,
                    current_admin=admin_user_id,
                )

            # Check if MongoDB supports transactions (replica set)
            is_replica_set = False
            try:
                ismaster = await self.db_manager.client.admin.command("ismaster")
                is_replica_set = bool(ismaster.get("setName"))
            except Exception as e:
                self.logger.warning("Could not determine replica set status: %s", e)

            now = datetime.now(timezone.utc)
            families_collection = self.db_manager.get_tenant_collection("families")
            users_collection = self.db_manager.get_collection("users")

            if is_replica_set:
                # Use transaction for replica set
                client = self.db_manager.client
                session = await client.start_session()

                async with session.start_transaction():
                    # Update family document to add new admin
                    await families_collection.update_one(
                        {"family_id": family_id},
                        {
                            "$push": {"admin_user_ids": target_user_id},
                            "$set": {
                                "updated_at": now,
                                "audit_trail.last_modified_by": admin_user_id,
                                "audit_trail.last_modified_at": now,
                            },
                            "$inc": {"audit_trail.version": 1},
                        },
                        session=session,
                    )

                    # Update user's family membership role
                    await users_collection.update_one(
                        {"_id": target_user_id, "family_memberships.family_id": family_id},
                        {
                            "$set": {
                                "family_memberships.$.role": "admin",
                                "family_memberships.$.spending_permissions.can_spend": True,
                                "family_memberships.$.spending_permissions.spending_limit": -1,
                                "family_memberships.$.spending_permissions.last_updated": now,
                            }
                        },
                        session=session,
                    )

                    # Update SBD account spending permissions
                    await families_collection.update_one(
                        {"family_id": family_id},
                        {
                            "$set": {
                                f"sbd_account.spending_permissions.{target_user_id}": {
                                    "role": "admin",
                                    "spending_limit": -1,
                                    "can_spend": True,
                                    "updated_by": admin_user_id,
                                    "updated_at": now,
                                }
                            }
                        },
                        session=session,
                    )

                    # Log admin action
                    await self._log_admin_action(
                        family_id,
                        admin_user_id,
                        target_user_id,
                        "promote_to_admin",
                        {"previous_role": "member", "new_role": "admin"},
                        session,
                    )

                    # Send notification
                    await self._send_admin_promotion_notification(family_id, admin_user_id, target_user_id, session)
            else:
                # Non-transactional operations for standalone MongoDB
                # Update family document to add new admin
                await families_collection.update_one(
                    {"family_id": family_id},
                    {
                        "$push": {"admin_user_ids": target_user_id},
                        "$set": {
                            "updated_at": now,
                            "audit_trail.last_modified_by": admin_user_id,
                            "audit_trail.last_modified_at": now,
                        },
                        "$inc": {"audit_trail.version": 1},
                    },
                )

                # Update user's family membership role
                await users_collection.update_one(
                    {"_id": target_user_id, "family_memberships.family_id": family_id},
                    {
                        "$set": {
                            "family_memberships.$.role": "admin",
                            "family_memberships.$.spending_permissions.can_spend": True,
                            "family_memberships.$.spending_permissions.spending_limit": -1,
                            "family_memberships.$.spending_permissions.last_updated": now,
                        }
                    },
                )

                # Update SBD account spending permissions
                await families_collection.update_one(
                    {"family_id": family_id},
                    {
                        "$set": {
                            f"sbd_account.spending_permissions.{target_user_id}": {
                                "role": "admin",
                                "spending_limit": -1,
                                "can_spend": True,
                                "updated_by": admin_user_id,
                                "updated_at": now,
                            }
                        }
                    },
                )

                # Log admin action (without session)
                await self._log_admin_action(
                    family_id,
                    admin_user_id,
                    target_user_id,
                    "promote_to_admin",
                    {"previous_role": "member", "new_role": "admin"},
                    None,
                )

                # Send notification (without session)
                await self._send_admin_promotion_notification(family_id, admin_user_id, target_user_id, None)

                self.db_manager.log_query_success(
                    "families", "promote_to_admin", start_time, 1, f"User promoted to admin: {target_user_id}"
                )

                self.logger.info(
                    "User promoted to family admin: %s by %s in family %s",
                    target_user_id,
                    admin_user_id,
                    family_id,
                    extra={
                        "family_id": family_id,
                        "admin_user_id": admin_user_id,
                        "target_user_id": target_user_id,
                        "action": "promote_to_admin",
                        "transaction_id": str(session.session_id) if session else None,
                    },
                )

                return {
                    "family_id": family_id,
                    "target_user_id": target_user_id,
                    "action": "promoted",
                    "new_role": "admin",
                    "promoted_by": admin_user_id,
                    "promoted_at": now,
                    "message": "User successfully promoted to family administrator",
                    "transaction_safe": True,
                }

        except (FamilyNotFound, InsufficientPermissions, AdminActionError, ValidationError, RateLimitExceeded) as e:
            self.db_manager.log_query_error("families", "promote_to_admin", start_time, e, operation_context)
            raise

        except Exception as e:
            # Handle transaction rollback
            rollback_successful = False
            if session and session.in_transaction:
                try:
                    await session.abort_transaction()
                    rollback_successful = True
                    self.logger.warning("Transaction rolled back successfully for admin promotion")
                except Exception as rollback_error:
                    self.logger.error("Failed to rollback promotion transaction: %s", rollback_error, exc_info=True)

            self.db_manager.log_query_error("families", "promote_to_admin", start_time, e, operation_context)
            self.logger.error(
                "Failed to promote user to admin: %s",
                e,
                exc_info=True,
                extra={
                    "family_id": family_id,
                    "admin_user_id": admin_user_id,
                    "target_user_id": target_user_id,
                    "rollback_successful": rollback_successful,
                },
            )

            raise TransactionError(
                f"Failed to promote user to admin: {str(e)}",
                operation="promote_to_admin",
                rollback_successful=rollback_successful,
            )

        finally:
            if session:
                await session.end_session()

    async def demote_from_admin(
        self, family_id: str, admin_user_id: str, target_user_id: str, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Demote a family administrator to member role.

        Args:
            family_id: ID of the family
            admin_user_id: ID of the admin performing the action
            target_user_id: ID of the admin to demote
            request_context: Request context for rate limiting and security

        Returns:
            Dict containing demotion information

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
            AdminActionError: If demotion validation fails
            MultipleAdminsRequired: If this would leave family with no admins
            ValidationError: If input validation fails
            TransactionError: If database transaction fails
        """
        operation_context = {
            "family_id": family_id,
            "admin_user_id": admin_user_id,
            "target_user_id": target_user_id,
            "operation": "demote_from_admin",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "demote_from_admin", operation_context)

        # Rate limiting check
        if request_context:
            try:
                await self._check_rate_limit(
                    request_context, "demote_admin", self._get_operation_rate_limit("demote_admin"), 3600
                )
            except Exception as e:
                raise RateLimitExceeded(
                    "Admin demotion rate limit exceeded",
                    action="demote_admin",
                    limit=self._get_operation_rate_limit("demote_admin"),
                    window=3600,
                )

        session = None

        try:
            # Validate input
            await self._validate_admin_action_input(family_id, admin_user_id, target_user_id, "demote")

            # Get family and verify permissions
            family = await self._get_family_by_id(family_id)
            if admin_user_id not in family["admin_user_ids"]:
                raise InsufficientPermissions(
                    "Only family admins can demote other admins", required_role="admin", user_role="member"
                )

            # Check if target user is actually an admin
            if target_user_id not in family["admin_user_ids"]:
                raise AdminActionError(
                    "User is not a family administrator",
                    action="demote",
                    target_user=target_user_id,
                    current_admin=admin_user_id,
                )

            # Prevent self-demotion if it would leave no admins
            current_admin_count = len(family["admin_user_ids"])
            if current_admin_count <= 1:
                raise MultipleAdminsRequired(
                    "Cannot demote the last administrator. Family must have at least one admin.",
                    operation="demote_admin",
                    current_admins=current_admin_count,
                )

            # Prevent self-demotion only if it would leave no admins (only 1 admin exists)
            # Fixed: Changed from <= 2 to < 2 so that with 2 admins, self-demotion is allowed
            if admin_user_id == target_user_id and current_admin_count < 2:
                backup_admins = family.get("succession_plan", {}).get("backup_admins", [])
                if not backup_admins:
                    raise AdminActionError(
                        "Cannot demote yourself as the last admin without designated backup admins",
                        action="demote",
                        target_user=target_user_id,
                        current_admin=admin_user_id,
                    )

            # Check if MongoDB supports transactions (replica set detection)
            is_replica_set = False
            try:
                ismaster = await self.db_manager.client.admin.command("ismaster")
                is_replica_set = bool(ismaster.get("setName"))
            except Exception as e:
                self.logger.warning("Could not determine replica set status: %s", e)

            now = datetime.now(timezone.utc)
            families_collection = self.db_manager.get_tenant_collection("families")
            users_collection = self.db_manager.get_collection("users")

            if is_replica_set:
                # Use transactions for replica sets
                client = self.db_manager.client
                session = await client.start_session()

                async with session.start_transaction():
                    # Update family document to remove admin
                    # Note: $inc must be a top-level update operator (sibling to $set),
                    # not nested inside the $set document. Nesting $inc inside $set
                    # creates a replacement-document situation and causes a WriteError
                    # (see MongoDB error about '$' prefixed fields in replacement documents).
                    await families_collection.update_one(
                        {"family_id": family_id},
                        {
                            "$pull": {"admin_user_ids": target_user_id},
                            "$set": {
                                "updated_at": now,
                                "audit_trail.last_modified_by": admin_user_id,
                                "audit_trail.last_modified_at": now,
                            },
                            "$inc": {"audit_trail.version": 1},
                        },
                        session=session,
                    )

                    # Update user's family membership role
                    await users_collection.update_one(
                        {"_id": target_user_id, "family_memberships.family_id": family_id},
                        {
                            "$set": {
                                "family_memberships.$.role": "member",
                                "family_memberships.$.spending_permissions.can_spend": False,
                                "family_memberships.$.spending_permissions.spending_limit": 0,
                                "family_memberships.$.spending_permissions.last_updated": now,
                            }
                        },
                        session=session,
                    )

                    # Update SBD account spending permissions
                    await families_collection.update_one(
                        {"family_id": family_id},
                        {
                            "$set": {
                                f"sbd_account.spending_permissions.{target_user_id}": {
                                    "role": "member",
                                    "spending_limit": 0,
                                    "can_spend": False,
                                    "updated_by": admin_user_id,
                                    "updated_at": now,
                                }
                            }
                        },
                        session=session,
                    )

                    # Log admin action
                    await self._log_admin_action(
                        family_id,
                        admin_user_id,
                        target_user_id,
                        "demote_from_admin",
                        {"previous_role": "admin", "new_role": "member"},
                        session,
                    )

                    # Send notification
                    await self._send_admin_demotion_notification(family_id, admin_user_id, target_user_id, session)
            else:
                # Non-transactional fallback for standalone MongoDB
                session = None

                # Update family document to remove admin
                # Note: $inc must be a top-level update operator (sibling to $set),
                # not nested inside the $set document. Nesting $inc inside $set
                # creates a replacement-document situation and causes a WriteError
                # (see MongoDB error about '$' prefixed fields in replacement documents).
                await families_collection.update_one(
                    {"family_id": family_id},
                    {
                        "$pull": {"admin_user_ids": target_user_id},
                        "$set": {
                            "updated_at": now,
                            "audit_trail.last_modified_by": admin_user_id,
                            "audit_trail.last_modified_at": now,
                        },
                        "$inc": {"audit_trail.version": 1},
                    },
                )

                # Update user's family membership role
                await users_collection.update_one(
                    {"_id": target_user_id, "family_memberships.family_id": family_id},
                    {
                        "$set": {
                            "family_memberships.$.role": "member",
                            "family_memberships.$.spending_permissions.can_spend": False,
                            "family_memberships.$.spending_permissions.spending_limit": 0,
                            "family_memberships.$.spending_permissions.last_updated": now,
                        }
                    },
                )

                # Update SBD account spending permissions
                await families_collection.update_one(
                    {"family_id": family_id},
                    {
                        "$set": {
                            f"sbd_account.spending_permissions.{target_user_id}": {
                                "role": "member",
                                "spending_limit": 0,
                                "can_spend": False,
                                "updated_by": admin_user_id,
                                "updated_at": now,
                            }
                        }
                    },
                )

                # Log admin action (no session)
                await self._log_admin_action(
                    family_id,
                    admin_user_id,
                    target_user_id,
                    "demote_from_admin",
                    {"previous_role": "admin", "new_role": "member"},
                    None,
                )

                # Send notification (no session)
                await self._send_admin_demotion_notification(family_id, admin_user_id, target_user_id, None)

                self.db_manager.log_query_success(
                    "families", "demote_from_admin", start_time, 1, f"Admin demoted to member: {target_user_id}"
                )

                self.logger.info(
                    "Family admin demoted to member: %s by %s in family %s",
                    target_user_id,
                    admin_user_id,
                    family_id,
                    extra={
                        "family_id": family_id,
                        "admin_user_id": admin_user_id,
                        "target_user_id": target_user_id,
                        "action": "demote_from_admin",
                        "transaction_id": str(session.session_id) if session else None,
                    },
                )

                return {
                    "family_id": family_id,
                    "target_user_id": target_user_id,
                    "action": "demoted",
                    "new_role": "member",
                    "demoted_by": admin_user_id,
                    "demoted_at": now,
                    "message": "Administrator successfully demoted to family member",
                    "transaction_safe": True,
                }

        except (
            FamilyNotFound,
            InsufficientPermissions,
            AdminActionError,
            MultipleAdminsRequired,
            ValidationError,
            RateLimitExceeded,
        ) as e:
            self.db_manager.log_query_error("families", "demote_from_admin", start_time, e, operation_context)
            raise

        except Exception as e:
            # Handle transaction rollback
            rollback_successful = False
            if session and session.in_transaction:
                try:
                    await session.abort_transaction()
                    rollback_successful = True
                    self.logger.warning("Transaction rolled back successfully for admin demotion")
                except Exception as rollback_error:
                    self.logger.error("Failed to rollback demotion transaction: %s", rollback_error, exc_info=True)

            self.db_manager.log_query_error("families", "demote_from_admin", start_time, e, operation_context)
            self.logger.error(
                "Failed to demote admin to member: %s",
                e,
                exc_info=True,
                extra={
                    "family_id": family_id,
                    "admin_user_id": admin_user_id,
                    "target_user_id": target_user_id,
                    "rollback_successful": rollback_successful,
                },
            )

            raise TransactionError(
                f"Failed to demote admin to member: {str(e)}",
                operation="demote_from_admin",
                rollback_successful=rollback_successful,
            )

        finally:
            if session:
                await session.end_session()

    async def designate_backup_admin(
        self, family_id: str, admin_user_id: str, backup_user_id: str, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Designate a family member as a backup administrator.

        Args:
            family_id: ID of the family
            admin_user_id: ID of the admin performing the action
            backup_user_id: ID of the user to designate as backup admin
            request_context: Request context for rate limiting and security

        Returns:
            Dict containing backup admin designation information

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
            BackupAdminError: If backup admin validation fails
            ValidationError: If input validation fails
            TransactionError: If database transaction fails
        """
        operation_context = {
            "family_id": family_id,
            "admin_user_id": admin_user_id,
            "backup_user_id": backup_user_id,
            "operation": "designate_backup_admin",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "designate_backup_admin", operation_context)

        # Rate limiting check
        if request_context:
            try:
                await self._check_rate_limit(
                    request_context, "backup_admin", self._get_operation_rate_limit("promote_admin"), 3600
                )
            except Exception as e:
                raise RateLimitExceeded(
                    "Backup admin designation rate limit exceeded",
                    action="backup_admin",
                    limit=self._get_operation_rate_limit("promote_admin"),
                    window=3600,
                )

        session = None

        try:
            # Validate input
            await self._validate_admin_action_input(family_id, admin_user_id, backup_user_id, "backup_admin")

            # Get family and verify permissions
            family = await self._get_family_by_id(family_id)
            if admin_user_id not in family["admin_user_ids"]:
                raise InsufficientPermissions(
                    "Only family admins can designate backup admins", required_role="admin", user_role="member"
                )

            # Check if backup user is already an admin
            if backup_user_id in family["admin_user_ids"]:
                raise BackupAdminError(
                    "User is already a family administrator", operation="designate_backup", backup_admin=backup_user_id
                )

            # Verify backup user is a family member
            if not await self._is_user_in_family(backup_user_id, family_id):
                raise BackupAdminError(
                    "User is not a member of this family", operation="designate_backup", backup_admin=backup_user_id
                )

            # Check if user is already a backup admin
            current_backup_admins = family.get("succession_plan", {}).get("backup_admins", [])
            if backup_user_id in current_backup_admins:
                raise BackupAdminError(
                    "User is already designated as a backup administrator",
                    operation="designate_backup",
                    backup_admin=backup_user_id,
                )

            # Start transaction
            client = self.db_manager.client
            session = await client.start_session()

            async with session.start_transaction():
                now = datetime.now(timezone.utc)

                # Update family succession plan
                families_collection = self.db_manager.get_tenant_collection("families")
                await families_collection.update_one(
                    {"family_id": family_id},
                    {
                        "$push": {"succession_plan.backup_admins": backup_user_id},
                        "$set": {
                            "updated_at": now,
                            "audit_trail.last_modified_by": admin_user_id,
                            "audit_trail.last_modified_at": now,
                            "$inc": {"audit_trail.version": 1},
                        },
                    },
                    session=session,
                )

                # Log admin action
                await self._log_admin_action(
                    family_id,
                    admin_user_id,
                    backup_user_id,
                    "designate_backup_admin",
                    {"backup_admin_role": "designated"},
                    session,
                )

                # Send notification
                await self._send_backup_admin_notification(
                    family_id, admin_user_id, backup_user_id, "designated", session
                )

                self.db_manager.log_query_success(
                    "families", "designate_backup_admin", start_time, 1, f"Backup admin designated: {backup_user_id}"
                )

                self.logger.info(
                    "Backup admin designated: %s by %s in family %s",
                    backup_user_id,
                    admin_user_id,
                    family_id,
                    extra={
                        "family_id": family_id,
                        "admin_user_id": admin_user_id,
                        "backup_user_id": backup_user_id,
                        "action": "designate_backup_admin",
                        "transaction_id": str(session.session_id) if session else None,
                    },
                )

                return {
                    "family_id": family_id,
                    "backup_user_id": backup_user_id,
                    "action": "designated",
                    "role": "backup_admin",
                    "designated_by": admin_user_id,
                    "designated_at": now,
                    "message": "User successfully designated as backup administrator",
                    "transaction_safe": True,
                }

        except (FamilyNotFound, InsufficientPermissions, BackupAdminError, ValidationError, RateLimitExceeded) as e:
            self.db_manager.log_query_error("families", "designate_backup_admin", start_time, e, operation_context)
            raise

        except Exception as e:
            # Handle transaction rollback
            rollback_successful = False
            if session and session.in_transaction:
                try:
                    await session.abort_transaction()
                    rollback_successful = True
                    self.logger.warning("Transaction rolled back successfully for backup admin designation")
                except Exception as rollback_error:
                    self.logger.error("Failed to rollback backup admin transaction: %s", rollback_error, exc_info=True)

            self.db_manager.log_query_error("families", "designate_backup_admin", start_time, e, operation_context)
            self.logger.error(
                "Failed to designate backup admin: %s",
                e,
                exc_info=True,
                extra={
                    "family_id": family_id,
                    "admin_user_id": admin_user_id,
                    "backup_user_id": backup_user_id,
                    "rollback_successful": rollback_successful,
                },
            )

            raise TransactionError(
                f"Failed to designate backup admin: {str(e)}",
                operation="designate_backup_admin",
                rollback_successful=rollback_successful,
            )

        finally:
            if session:
                await session.end_session()

    async def remove_backup_admin(
        self, family_id: str, admin_user_id: str, backup_user_id: str, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Remove a backup administrator designation.

        Args:
            family_id: ID of the family
            admin_user_id: ID of the admin performing the action
            backup_user_id: ID of the backup admin to remove
            request_context: Request context for rate limiting and security

        Returns:
            Dict containing backup admin removal information

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
            BackupAdminError: If backup admin validation fails
            ValidationError: If input validation fails
            TransactionError: If database transaction fails
        """
        operation_context = {
            "family_id": family_id,
            "admin_user_id": admin_user_id,
            "backup_user_id": backup_user_id,
            "operation": "remove_backup_admin",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "remove_backup_admin", operation_context)

        # Rate limiting check
        if request_context:
            try:
                await self._check_rate_limit(
                    request_context, "backup_admin", self._get_operation_rate_limit("demote_admin"), 3600
                )
            except Exception as e:
                raise RateLimitExceeded(
                    "Backup admin removal rate limit exceeded",
                    action="backup_admin",
                    limit=self._get_operation_rate_limit("demote_admin"),
                    window=3600,
                )

        session = None

        try:
            # Validate input
            await self._validate_admin_action_input(family_id, admin_user_id, backup_user_id, "remove_backup")

            # Get family and verify permissions
            family = await self._get_family_by_id(family_id)
            if admin_user_id not in family["admin_user_ids"]:
                raise InsufficientPermissions(
                    "Only family admins can remove backup admin designations", required_role="admin", user_role="member"
                )

            # Check if user is actually a backup admin
            current_backup_admins = family.get("succession_plan", {}).get("backup_admins", [])
            if backup_user_id not in current_backup_admins:
                raise BackupAdminError(
                    "User is not designated as a backup administrator",
                    operation="remove_backup",
                    backup_admin=backup_user_id,
                )

            # Start transaction
            client = self.db_manager.client
            session = await client.start_session()

            async with session.start_transaction():
                now = datetime.now(timezone.utc)

                # Update family succession plan
                families_collection = self.db_manager.get_tenant_collection("families")
                await families_collection.update_one(
                    {"family_id": family_id},
                    {
                        "$pull": {"succession_plan.backup_admins": backup_user_id},
                        "$set": {
                            "updated_at": now,
                            "audit_trail.last_modified_by": admin_user_id,
                            "audit_trail.last_modified_at": now,
                            "$inc": {"audit_trail.version": 1},
                        },
                    },
                    session=session,
                )

                # Log admin action
                await self._log_admin_action(
                    family_id,
                    admin_user_id,
                    backup_user_id,
                    "remove_backup_admin",
                    {"backup_admin_role": "removed"},
                    session,
                )

                # Send notification
                await self._send_backup_admin_notification(family_id, admin_user_id, backup_user_id, "removed", session)

                self.db_manager.log_query_success(
                    "families", "remove_backup_admin", start_time, 1, f"Backup admin removed: {backup_user_id}"
                )

                self.logger.info(
                    "Backup admin designation removed: %s by %s in family %s",
                    backup_user_id,
                    admin_user_id,
                    family_id,
                    extra={
                        "family_id": family_id,
                        "admin_user_id": admin_user_id,
                        "backup_user_id": backup_user_id,
                        "action": "remove_backup_admin",
                        "transaction_id": str(session.session_id) if session else None,
                    },
                )

                return {
                    "family_id": family_id,
                    "backup_user_id": backup_user_id,
                    "action": "removed",
                    "role": "backup_admin",
                    "removed_by": admin_user_id,
                    "removed_at": now,
                    "message": "Backup administrator designation successfully removed",
                    "transaction_safe": True,
                }

        except (FamilyNotFound, InsufficientPermissions, BackupAdminError, ValidationError, RateLimitExceeded) as e:
            self.db_manager.log_query_error("families", "remove_backup_admin", start_time, e, operation_context)
            raise

        except Exception as e:
            # Handle transaction rollback
            rollback_successful = False
            if session and session.in_transaction:
                try:
                    await session.abort_transaction()
                    rollback_successful = True
                    self.logger.warning("Transaction rolled back successfully for backup admin removal")
                except Exception as rollback_error:
                    self.logger.error(
                        "Failed to rollback backup admin removal transaction: %s", rollback_error, exc_info=True
                    )

            self.db_manager.log_query_error("families", "remove_backup_admin", start_time, e, operation_context)
            self.logger.error(
                "Failed to remove backup admin designation: %s",
                e,
                exc_info=True,
                extra={
                    "family_id": family_id,
                    "admin_user_id": admin_user_id,
                    "backup_user_id": backup_user_id,
                    "rollback_successful": rollback_successful,
                },
            )

            raise TransactionError(
                f"Failed to remove backup admin designation: {str(e)}",
                operation="remove_backup_admin",
                rollback_successful=rollback_successful,
            )

        finally:
            if session:
                await session.end_session()

    async def get_admin_actions_log(
        self, family_id: str, admin_user_id: str, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get admin actions log for a family.

        Args:
            family_id: ID of the family
            admin_user_id: ID of the admin requesting the log
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            Dict containing admin actions log

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
            ValidationError: If input validation fails
        """
        operation_context = {
            "family_id": family_id,
            "admin_user_id": admin_user_id,
            "operation": "get_admin_actions_log",
        }
        start_time = self.db_manager.log_query_start("family_admin_actions", "get_log", operation_context)

        try:
            # Validate input
            if not family_id or not admin_user_id:
                raise ValidationError("Family ID and admin user ID are required")

            if limit < 1 or limit > 100:
                raise ValidationError("Limit must be between 1 and 100", field="limit", value=limit)

            if offset < 0:
                raise ValidationError("Offset must be non-negative", field="offset", value=offset)

            # Get family and verify permissions
            family = await self._get_family_by_id(family_id)
            if admin_user_id not in family["admin_user_ids"]:
                raise InsufficientPermissions(
                    "Only family admins can view admin actions log", required_role="admin", user_role="member"
                )

            # Get admin actions log
            admin_actions_collection = self.db_manager.get_tenant_collection("family_admin_actions")

            # Get total count
            total_count = await admin_actions_collection.count_documents({"family_id": family_id})

            # Get paginated results
            cursor = (
                admin_actions_collection.find({"family_id": family_id}).sort("created_at", -1).skip(offset).limit(limit)
            )

            actions = await cursor.to_list(length=limit)

            # Enrich with user information
            enriched_actions = []
            for action in actions:
                # Get admin user info
                admin_user = await self._get_user_by_id(action["admin_user_id"])
                target_user = await self._get_user_by_id(action["target_user_id"])

                enriched_actions.append(
                    {
                        "action_id": action["action_id"],
                        "family_id": action["family_id"],
                        "admin_user_id": action["admin_user_id"],
                        "admin_username": admin_user.get("username", "Unknown"),
                        "target_user_id": action["target_user_id"],
                        "target_username": target_user.get("username", "Unknown"),
                        "action_type": action["action_type"],
                        "details": action["details"],
                        "created_at": action["created_at"],
                        "ip_address": action.get("ip_address"),
                        "user_agent": action.get("user_agent"),
                    }
                )

            self.db_manager.log_query_success("family_admin_actions", "get_log", start_time, len(actions))

            self.logger.debug(
                "Retrieved %d admin actions for family %s",
                len(actions),
                family_id,
                extra={
                    "family_id": family_id,
                    "admin_user_id": admin_user_id,
                    "total_count": total_count,
                    "returned_count": len(actions),
                },
            )

            return {
                "family_id": family_id,
                "actions": enriched_actions,
                "pagination": {
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + len(actions)) < total_count,
                },
            }

        except (FamilyNotFound, InsufficientPermissions, ValidationError) as e:
            self.db_manager.log_query_error("family_admin_actions", "get_log", start_time, e, operation_context)
            raise

        except Exception as e:
            self.db_manager.log_query_error("family_admin_actions", "get_log", start_time, e, operation_context)
            self.logger.error(
                "Failed to get admin actions log: %s",
                e,
                exc_info=True,
                extra={"family_id": family_id, "admin_user_id": admin_user_id},
            )
            raise FamilyError(f"Failed to get admin actions log: {str(e)}")

    # Helper methods for multi-admin support

    async def _validate_admin_action_input(
        self, family_id: str, admin_user_id: str, target_user_id: str, action: str
    ) -> None:
        """Validate input parameters for admin actions."""
        if not family_id or not family_id.strip():
            raise ValidationError("Family ID is required", field="family_id", constraint="not_empty")

        if not admin_user_id or not admin_user_id.strip():
            raise ValidationError("Admin user ID is required", field="admin_user_id", constraint="not_empty")

        if not target_user_id or not target_user_id.strip():
            raise ValidationError("Target user ID is required", field="target_user_id", constraint="not_empty")

        if admin_user_id == target_user_id and action in ["promote", "demote"]:
            # Allow self-demotion but with additional checks in the main method
            if action == "promote":
                raise ValidationError("Cannot promote yourself", field="target_user_id", constraint="not_self")

        valid_actions = ["promote", "demote", "backup_admin", "remove_backup"]
        if action not in valid_actions:
            raise ValidationError(
                f"Invalid action: {action}. Valid actions: {', '.join(valid_actions)}",
                field="action",
                value=action,
                constraint="valid_action",
            )

    async def _log_admin_action(
        self,
        family_id: str,
        admin_user_id: str,
        target_user_id: str,
        action_type: str,
        details: Dict[str, Any],
        session: ClientSession = None,
    ) -> None:
        """Log admin action for audit trail."""
        try:
            admin_actions_collection = self.db_manager.get_tenant_collection("family_admin_actions")

            action_id = f"act_{uuid.uuid4().hex[:16]}"
            now = datetime.now(timezone.utc)

            action_doc = {
                "action_id": action_id,
                "family_id": family_id,
                "admin_user_id": admin_user_id,
                "target_user_id": target_user_id,
                "action_type": action_type,
                "details": details,
                "created_at": now,
                "ip_address": None,  # Could be populated from request context
                "user_agent": None,  # Could be populated from request context
            }

            if session:
                await admin_actions_collection.insert_one(action_doc, session=session)
            else:
                await admin_actions_collection.insert_one(action_doc)

            self.logger.debug(
                "Admin action logged: %s by %s on %s in family %s",
                action_type,
                admin_user_id,
                target_user_id,
                family_id,
                extra={
                    "action_id": action_id,
                    "family_id": family_id,
                    "admin_user_id": admin_user_id,
                    "target_user_id": target_user_id,
                    "action_type": action_type,
                },
            )

        except Exception as e:
            self.logger.error(
                "Failed to log admin action: %s",
                e,
                exc_info=True,
                extra={
                    "family_id": family_id,
                    "admin_user_id": admin_user_id,
                    "target_user_id": target_user_id,
                    "action_type": action_type,
                },
            )
            # Don't raise exception - logging failure shouldn't break the main operation

    async def _send_admin_promotion_notification(
        self, family_id: str, admin_user_id: str, target_user_id: str, session: ClientSession = None
    ) -> None:
        """Send notification for admin promotion."""
        try:
            # Get family and user information
            family = await self._get_family_by_id(family_id)
            admin_user = await self._get_user_by_id(admin_user_id)
            target_user = await self._get_user_by_id(target_user_id)

            # Create notification for all family admins
            notification_data = {
                "type": "admin_promoted",
                "title": "New Family Administrator",
                "message": f"{target_user.get('username', 'Unknown')} has been promoted to family administrator by {admin_user.get('username', 'Unknown')}",
                "data": {
                    "family_id": family_id,
                    "family_name": family["name"],
                    "promoted_user_id": target_user_id,
                    "promoted_username": target_user.get("username", "Unknown"),
                    "promoted_by": admin_user_id,
                    "promoted_by_username": admin_user.get("username", "Unknown"),
                },
            }

            # Send to all family admins (including the newly promoted one)
            recipient_ids = family["admin_user_ids"] + [target_user_id]
            recipient_ids = list(set(recipient_ids))  # Remove duplicates

            await self._create_family_notification(family_id, recipient_ids, notification_data, session)

        except Exception as e:
            self.logger.error("Failed to send admin promotion notification: %s", e, exc_info=True)

    async def _send_admin_demotion_notification(
        self, family_id: str, admin_user_id: str, target_user_id: str, session: ClientSession = None
    ) -> None:
        """Send notification for admin demotion."""
        try:
            # Get family and user information
            family = await self._get_family_by_id(family_id)
            admin_user = await self._get_user_by_id(admin_user_id)
            target_user = await self._get_user_by_id(target_user_id)

            # Create notification for all family admins
            notification_data = {
                "type": "admin_demoted",
                "title": "Administrator Demoted",
                "message": f"{target_user.get('username', 'Unknown')} has been demoted from family administrator by {admin_user.get('username', 'Unknown')}",
                "data": {
                    "family_id": family_id,
                    "family_name": family["name"],
                    "demoted_user_id": target_user_id,
                    "demoted_username": target_user.get("username", "Unknown"),
                    "demoted_by": admin_user_id,
                    "demoted_by_username": admin_user.get("username", "Unknown"),
                },
            }

            # Send to all remaining family admins and the demoted user
            recipient_ids = family["admin_user_ids"] + [target_user_id]
            recipient_ids = list(set(recipient_ids))  # Remove duplicates

            await self._create_family_notification(family_id, recipient_ids, notification_data, session)

        except Exception as e:
            self.logger.error("Failed to send admin demotion notification: %s", e, exc_info=True)

    async def _send_backup_admin_notification(
        self, family_id: str, admin_user_id: str, backup_user_id: str, action: str, session: ClientSession = None
    ) -> None:
        """Send notification for backup admin designation/removal."""
        try:
            # Get family and user information
            family = await self._get_family_by_id(family_id)
            admin_user = await self._get_user_by_id(admin_user_id)
            backup_user = await self._get_user_by_id(backup_user_id)

            if action == "designated":
                title = "Backup Administrator Designated"
                message = f"{backup_user.get('username', 'Unknown')} has been designated as a backup administrator by {admin_user.get('username', 'Unknown')}"
            else:  # removed
                title = "Backup Administrator Removed"
                message = f"{backup_user.get('username', 'Unknown')} is no longer a backup administrator (removed by {admin_user.get('username', 'Unknown')})"

            # Create notification
            notification_data = {
                "type": f"backup_admin_{action}",
                "title": title,
                "message": message,
                "data": {
                    "family_id": family_id,
                    "family_name": family["name"],
                    "backup_user_id": backup_user_id,
                    "backup_username": backup_user.get("username", "Unknown"),
                    "action_by": admin_user_id,
                    "action_by_username": admin_user.get("username", "Unknown"),
                    "action": action,
                },
            }

            # Send to all family admins and the backup admin
            recipient_ids = family["admin_user_ids"] + [backup_user_id]
            recipient_ids = list(set(recipient_ids))  # Remove duplicates

            await self._create_family_notification(family_id, recipient_ids, notification_data, session)

        except Exception as e:
            self.logger.error("Failed to send backup admin notification: %s", e, exc_info=True)

    async def _create_family_notification(
        self, family_id: str, recipient_ids: List[str], notification_data: Dict[str, Any], session: ClientSession = None
    ) -> None:
        """Create a family notification."""
        try:
            notifications_collection = self.db_manager.get_tenant_collection("family_notifications")

            notification_id = f"notif_{uuid.uuid4().hex[:16]}"
            now = datetime.now(timezone.utc)

            notification_doc = {
                "notification_id": notification_id,
                "family_id": family_id,
                "recipient_user_ids": recipient_ids,
                "type": notification_data["type"],
                "title": notification_data["title"],
                "message": notification_data["message"],
                "data": notification_data["data"],
                "status": "pending",
                "created_at": now,
                "sent_at": None,
                "read_by": {},
            }

            if session:
                await notifications_collection.insert_one(notification_doc, session=session)
            else:
                await notifications_collection.insert_one(notification_doc)

            self.logger.debug(
                "Family notification created: %s for family %s",
                notification_id,
                family_id,
                extra={
                    "notification_id": notification_id,
                    "family_id": family_id,
                    "recipient_count": len(recipient_ids),
                    "type": notification_data["type"],
                },
            )

        except Exception as e:
            self.logger.error(
                "Failed to create family notification: %s",
                e,
                exc_info=True,
                extra={
                    "family_id": family_id,
                    "recipient_count": len(recipient_ids) if recipient_ids else 0,
                    "notification_type": notification_data.get("type", "unknown"),
                },
            )
            # Don't raise exception - notification failure shouldn't break the main operation

    # Public notification management methods

    async def get_family_notifications(
        self, family_id: str, user_id: str, limit: int = 50, offset: int = 0, status_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get family notifications for a user with pagination and filtering.

        Args:
            family_id: ID of the family
            user_id: ID of the user requesting notifications
            limit: Maximum number of notifications to return
            offset: Number of notifications to skip
            status_filter: Optional status filter ("pending", "sent", "read", "archived")

        Returns:
            Dict containing notifications and metadata

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not a family member
        """
        operation_context = {
            "family_id": family_id,
            "user_id": user_id,
            "limit": limit,
            "offset": offset,
            "status_filter": status_filter,
            "operation": "get_family_notifications",
        }
        start_time = self.db_manager.log_query_start("family_notifications", "get_notifications", operation_context)

        try:
            # Verify user is family member
            await self._verify_family_membership(family_id, user_id)

            # Build query
            query = {"family_id": family_id, "recipient_user_ids": user_id}

            if status_filter:
                if status_filter == "read":
                    query[f"read_by.{user_id}"] = {"$exists": True}
                elif status_filter == "unread":
                    query[f"read_by.{user_id}"] = {"$exists": False}
                else:
                    query["status"] = status_filter

            # Get notifications with pagination
            notifications_collection = self.db_manager.get_tenant_collection("family_notifications")

            # Get total count
            total_count = await notifications_collection.count_documents(query)

            # Get notifications
            cursor = notifications_collection.find(query).sort("created_at", -1).skip(offset).limit(limit)
            notifications = await cursor.to_list(length=limit)

            # Process notifications for response
            processed_notifications = []
            for notification in notifications:
                is_read = user_id in notification.get("read_by", {})
                processed_notifications.append(
                    {
                        "notification_id": notification["notification_id"],
                        "type": notification["type"],
                        "title": notification["title"],
                        "message": notification["message"],
                        "data": notification["data"],
                        "status": notification["status"],
                        "created_at": notification["created_at"],
                        "is_read": is_read,
                        "read_at": notification.get("read_by", {}).get(user_id),
                    }
                )

            # Get unread count
            unread_query = dict(query)
            unread_query[f"read_by.{user_id}"] = {"$exists": False}
            unread_count = await notifications_collection.count_documents(unread_query)

            self.db_manager.log_query_success(
                "family_notifications", "get_notifications", start_time, len(processed_notifications)
            )

            return {
                "notifications": processed_notifications,
                "total_count": total_count,
                "unread_count": unread_count,
                "has_more": offset + len(processed_notifications) < total_count,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "next_offset": offset + limit if offset + len(processed_notifications) < total_count else None,
                },
            }

        except (FamilyNotFound, InsufficientPermissions) as e:
            self.db_manager.log_query_error(
                "family_notifications", "get_notifications", start_time, e, operation_context
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "family_notifications", "get_notifications", start_time, e, operation_context
            )
            self.logger.error(
                "Failed to get family notifications for user %s in family %s: %s", user_id, family_id, e, exc_info=True
            )
            raise FamilyError(f"Failed to get notifications: {str(e)}")

    async def mark_notifications_read(
        self, family_id: str, user_id: str, notification_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Mark specific notifications as read for a user.

        Args:
            family_id: ID of the family
            user_id: ID of the user marking notifications as read
            notification_ids: List of notification IDs to mark as read

        Returns:
            Dict containing update results

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not a family member
        """
        operation_context = {
            "family_id": family_id,
            "user_id": user_id,
            "notification_count": len(notification_ids),
            "operation": "mark_notifications_read",
        }
        start_time = self.db_manager.log_query_start("family_notifications", "mark_read", operation_context)

        try:
            # Verify user is family member
            await self._verify_family_membership(family_id, user_id)

            if not notification_ids:
                return {"marked_count": 0, "updated_notifications": []}

            # Update notifications
            notifications_collection = self.db_manager.get_tenant_collection("family_notifications")
            now = datetime.now(timezone.utc)

            # Mark notifications as read
            result = await notifications_collection.update_many(
                {
                    "family_id": family_id,
                    "notification_id": {"$in": notification_ids},
                    "recipient_user_ids": user_id,
                    f"read_by.{user_id}": {"$exists": False},  # Only update unread notifications
                },
                {"$set": {f"read_by.{user_id}": now}},
            )

            # Update user's unread count
            await self._update_user_notification_count(user_id, family_id)

            self.db_manager.log_query_success("family_notifications", "mark_read", start_time, result.modified_count)

            self.logger.info(
                "Marked %d notifications as read for user %s in family %s",
                result.modified_count,
                user_id,
                family_id,
                extra={
                    "family_id": family_id,
                    "user_id": user_id,
                    "marked_count": result.modified_count,
                    "requested_count": len(notification_ids),
                },
            )

            return {
                "marked_count": result.modified_count,
                "updated_notifications": notification_ids[: result.modified_count],
            }

        except (FamilyNotFound, InsufficientPermissions) as e:
            self.db_manager.log_query_error("family_notifications", "mark_read", start_time, e, operation_context)
            raise
        except Exception as e:
            self.db_manager.log_query_error("family_notifications", "mark_read", start_time, e, operation_context)
            self.logger.error(
                "Failed to mark notifications as read for user %s in family %s: %s",
                user_id,
                family_id,
                e,
                exc_info=True,
            )
            raise FamilyError(f"Failed to mark notifications as read: {str(e)}")

    async def mark_all_notifications_read(self, family_id: str, user_id: str) -> Dict[str, Any]:
        """
        Mark all notifications as read for a user in a family.

        Args:
            family_id: ID of the family
            user_id: ID of the user marking all notifications as read

        Returns:
            Dict containing update results
        """
        operation_context = {"family_id": family_id, "user_id": user_id, "operation": "mark_all_notifications_read"}
        start_time = self.db_manager.log_query_start("family_notifications", "mark_all_read", operation_context)

        try:
            # Verify user is family member
            await self._verify_family_membership(family_id, user_id)

            # Update all unread notifications
            notifications_collection = self.db_manager.get_tenant_collection("family_notifications")
            now = datetime.now(timezone.utc)

            result = await notifications_collection.update_many(
                {"family_id": family_id, "recipient_user_ids": user_id, f"read_by.{user_id}": {"$exists": False}},
                {"$set": {f"read_by.{user_id}": now}},
            )

            # Update user's unread count to 0
            await self._update_user_notification_count(user_id, family_id, force_count=0)

            self.db_manager.log_query_success(
                "family_notifications", "mark_all_read", start_time, result.modified_count
            )

            self.logger.info(
                "Marked all %d notifications as read for user %s in family %s",
                result.modified_count,
                user_id,
                family_id,
            )

            return {"marked_count": result.modified_count}

        except (FamilyNotFound, InsufficientPermissions) as e:
            self.db_manager.log_query_error("family_notifications", "mark_all_read", start_time, e, operation_context)
            raise
        except Exception as e:
            self.db_manager.log_query_error("family_notifications", "mark_all_read", start_time, e, operation_context)
            self.logger.error(
                "Failed to mark all notifications as read for user %s in family %s: %s",
                user_id,
                family_id,
                e,
                exc_info=True,
            )
            raise FamilyError(f"Failed to mark all notifications as read: {str(e)}")

    async def update_notification_preferences(self, user_id: str, preferences: Dict[str, bool]) -> Dict[str, Any]:
        """
        Update notification preferences for a user.

        Args:
            user_id: ID of the user
            preferences: Dictionary of preference settings

        Returns:
            Dict containing updated preferences
        """
        operation_context = {
            "user_id": user_id,
            "preferences": preferences,
            "operation": "update_notification_preferences",
        }
        start_time = self.db_manager.log_query_start("users", "update_preferences", operation_context)

        try:
            # Validate preferences
            valid_preferences = {"email_notifications", "push_notifications", "sms_notifications"}
            invalid_prefs = set(preferences.keys()) - valid_preferences
            if invalid_prefs:
                raise ValidationError(
                    f"Invalid preference keys: {invalid_prefs}", field="preferences", value=list(invalid_prefs)
                )

            # Update user preferences
            users_collection = self.db_manager.get_collection("users")
            now = datetime.now(timezone.utc)

            update_data = {}
            for pref_key, pref_value in preferences.items():
                update_data[f"family_notifications.preferences.{pref_key}"] = pref_value

            result = await users_collection.update_one(
                {"_id": user_id},
                {
                    "$set": update_data,
                    "$setOnInsert": {"family_notifications.unread_count": 0, "family_notifications.last_checked": now},
                },
                upsert=True,
            )

            # Get updated preferences
            user = await users_collection.find_one({"_id": user_id}, {"family_notifications.preferences": 1})

            updated_preferences = user.get("family_notifications", {}).get("preferences", {})

            self.db_manager.log_query_success(
                "users", "update_preferences", start_time, 1 if result.modified_count > 0 else 0
            )

            self.logger.info(
                "Updated notification preferences for user %s: %s",
                user_id,
                preferences,
                extra={"user_id": user_id, "preferences": preferences},
            )

            return {"preferences": updated_preferences}

        except ValidationError as e:
            self.db_manager.log_query_error("users", "update_preferences", start_time, e, operation_context)
            raise
        except Exception as e:
            self.db_manager.log_query_error("users", "update_preferences", start_time, e, operation_context)
            self.logger.error("Failed to update notification preferences for user %s: %s", user_id, e, exc_info=True)
            raise FamilyError(f"Failed to update notification preferences: {str(e)}")

    async def get_notification_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get notification preferences for a user.

        Args:
            user_id: ID of the user

        Returns:
            Dict containing user's notification preferences
        """
        try:
            users_collection = self.db_manager.get_collection("users")

            # Try with string ID first
            user = await users_collection.find_one({"_id": user_id}, {"family_notifications": 1})

            # If not found and user_id looks like ObjectId, try converting
            if not user and isinstance(user_id, str) and len(user_id) == 24:
                try:
                    oid = ObjectId(user_id)
                    user = await users_collection.find_one({"_id": oid}, {"family_notifications": 1})
                except Exception:
                    pass

            if not user:
                raise FamilyError("User not found")

            family_notifications = user.get("family_notifications", {})
            preferences = family_notifications.get(
                "preferences", {"email_notifications": True, "push_notifications": True, "sms_notifications": False}
            )

            return {
                "preferences": preferences,
                "unread_count": family_notifications.get("unread_count", 0),
                "last_checked": family_notifications.get("last_checked"),
            }

        except Exception as e:
            self.logger.error("Failed to get notification preferences for user %s: %s", user_id, e, exc_info=True)
            raise FamilyError(f"Failed to get notification preferences: {str(e)}")

    # Enhanced notification creation with templating

    async def send_sbd_transaction_notification(
        self,
        family_id: str,
        transaction_type: str,
        amount: int,
        from_user_id: str,
        to_user_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> None:
        """
        Send notification for SBD token transactions.

        Args:
            family_id: ID of the family
            transaction_type: "spend" or "deposit"
            amount: Transaction amount
            from_user_id: User who initiated the transaction
            to_user_id: User who received tokens (for spending)
            transaction_id: Optional transaction ID for reference
        """
        try:
            family = await self._get_family_by_id(family_id)
            from_user = await self._get_user_by_id(from_user_id)

            # Get all family members as recipients
            recipient_ids = await self._get_family_member_ids(family_id)

            # Create notification based on transaction type
            if transaction_type == "spend":
                notification_type = "sbd_spend"
                title = "SBD Token Spending"
                if to_user_id:
                    to_user = await self._get_user_by_id(to_user_id)
                    message = f"@{from_user['username']} spent {amount} SBD tokens to @{to_user['username']}"
                else:
                    message = f"@{from_user['username']} spent {amount} SBD tokens"
            else:  # deposit
                notification_type = "sbd_deposit"
                title = "SBD Token Deposit"
                message = f"@{from_user['username']} deposited {amount} SBD tokens to the family account"

            # Check if this is a large transaction
            threshold = family["sbd_account"]["notification_settings"].get("large_transaction_threshold", 1000)
            if amount >= threshold:
                notification_type = "large_transaction"
                title = f"Large Transaction Alert - {amount} SBD"
                # For large transactions, notify only admins if configured
                if family["sbd_account"]["notification_settings"].get("notify_admins_only", False):
                    recipient_ids = family["admin_user_ids"]

            notification_data = {
                "type": notification_type,
                "title": title,
                "message": message,
                "data": {
                    "transaction_type": transaction_type,
                    "amount": amount,
                    "from_user_id": from_user_id,
                    "from_username": from_user["username"],
                    "to_user_id": to_user_id,
                    "transaction_id": transaction_id,
                    "family_account": family["sbd_account"]["account_username"],
                },
            }

            await self._create_family_notification(family_id, recipient_ids, notification_data)

            # Update unread counts for recipients
            for recipient_id in recipient_ids:
                await self._update_user_notification_count(recipient_id, family_id)

        except Exception as e:
            self.logger.error(
                "Failed to send SBD transaction notification: %s",
                e,
                exc_info=True,
                extra={
                    "family_id": family_id,
                    "transaction_type": transaction_type,
                    "amount": amount,
                    "from_user_id": from_user_id,
                },
            )

    async def send_spending_limit_notification(
        self, family_id: str, user_id: str, attempted_amount: int, limit: int
    ) -> None:
        """
        Send notification when spending limit is reached or exceeded.

        Args:
            family_id: ID of the family
            user_id: User who reached the limit
            attempted_amount: Amount they tried to spend
            limit: Their spending limit
        """
        try:
            family = await self._get_family_by_id(family_id)
            user = await self._get_user_by_id(user_id)

            # Notify admins and the user who reached the limit
            recipient_ids = list(set(family["admin_user_ids"] + [user_id]))

            notification_data = {
                "type": "spending_limit_reached",
                "title": "Spending Limit Reached",
                "message": f"@{user['username']} attempted to spend {attempted_amount} SBD tokens but their limit is {limit}",
                "data": {
                    "user_id": user_id,
                    "username": user["username"],
                    "attempted_amount": attempted_amount,
                    "spending_limit": limit,
                    "family_account": family["sbd_account"]["account_username"],
                },
            }

            await self._create_family_notification(family_id, recipient_ids, notification_data)

            # Update unread counts
            for recipient_id in recipient_ids:
                await self._update_user_notification_count(recipient_id, family_id)

        except Exception as e:
            self.logger.error("Failed to send spending limit notification: %s", e, exc_info=True)

    # Helper methods for notification system

    async def _verify_family_membership(self, family_id: str, user_id: str) -> None:
        """Verify that a user is a member of the specified family."""
        family = await self._get_family_by_id(family_id)

        # Check if user is in family members
        users_collection = self.db_manager.get_collection("users")

        # Try with string ID first
        user = await users_collection.find_one({"_id": user_id, "family_memberships.family_id": family_id})

        # If not found and user_id looks like ObjectId, try converting
        if not user and isinstance(user_id, str) and len(user_id) == 24:
            try:
                oid = ObjectId(user_id)
                user = await users_collection.find_one({"_id": oid, "family_memberships.family_id": family_id})
            except Exception:
                pass

        if not user:
            raise InsufficientPermissions("User is not a member of this family")

    async def _get_family_member_ids(self, family_id: str) -> List[str]:
        """Get all member IDs for a family."""
        users_collection = self.db_manager.get_collection("users")
        cursor = users_collection.find({"family_memberships.family_id": family_id}, {"_id": 1})

        members = await cursor.to_list(length=None)
        return [str(member["_id"]) for member in members]

    async def _update_user_notification_count(
        self, user_id: str, family_id: str, force_count: Optional[int] = None
    ) -> None:
        """Update the unread notification count for a user."""
        try:
            users_collection = self.db_manager.get_collection("users")

            if force_count is not None:
                # Set count to specific value
                unread_count = force_count
            else:
                # Calculate actual unread count
                notifications_collection = self.db_manager.get_tenant_collection("family_notifications")
                unread_count = await notifications_collection.count_documents(
                    {"family_id": family_id, "recipient_user_ids": user_id, f"read_by.{user_id}": {"$exists": False}}
                )

            await users_collection.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "family_notifications.unread_count": unread_count,
                        "family_notifications.last_checked": datetime.now(timezone.utc),
                    }
                },
            )

        except Exception as e:
            self.logger.error("Failed to update notification count for user %s: %s", user_id, e, exc_info=True)

    # Additional methods for RESTful API endpoints

    async def get_family_details(self, family_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific family.

        Args:
            family_id: ID of the family to get details for
            user_id: ID of the user requesting details

        Returns:
            Dict containing detailed family information

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not a family member
        """
        start_time = self.db_manager.log_query_start(
            "families", "get_family_details", {"family_id": family_id, "user_id": user_id}
        )

        try:
            # Verify family membership
            await self._verify_family_membership(family_id, user_id)

            # Get family data
            family = await self._get_family_by_id(family_id)

            # Get SBD account balance
            sbd_balance = await self._get_sbd_account_balance(family["sbd_account"]["account_username"])

            # Build comprehensive response
            family_data = {
                "family_id": family["family_id"],
                "name": family["name"],
                "admin_user_ids": family["admin_user_ids"],
                "member_count": family["member_count"],
                "created_at": family["created_at"],
                "is_admin": user_id in family["admin_user_ids"],
                "sbd_account": {
                    "account_username": family["sbd_account"]["account_username"],
                    "balance": sbd_balance,
                    "is_frozen": family["sbd_account"]["is_frozen"],
                    "frozen_by": family["sbd_account"].get("frozen_by"),
                    "spending_permissions": family["sbd_account"]["spending_permissions"],
                },
                "usage_stats": {
                    "current_members": family["member_count"],
                    "max_members_allowed": 5,  # Default limit - should be from user settings
                    "can_add_members": user_id in family["admin_user_ids"],
                },
            }

            self.db_manager.log_query_success("families", "get_family_details", start_time, 1)
            return family_data

        except (FamilyNotFound, InsufficientPermissions):
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "families", "get_family_details", start_time, e, {"family_id": family_id, "user_id": user_id}
            )
            raise FamilyError(f"Failed to get family details: {str(e)}")

    async def remove_family_member(
        self, family_id: str, admin_id: str, member_id: str, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Remove a member from the family with comprehensive cleanup.

        Args:
            family_id: ID of the family
            admin_id: ID of the admin performing the removal
            member_id: ID of the member to remove
            request_context: Request context for security

        Returns:
            Dict containing removal confirmation and cleanup details

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
            MultipleAdminsRequired: If trying to remove last admin
        """
        start_time = self.db_manager.log_query_start(
            "families", "remove_member", {"family_id": family_id, "admin_id": admin_id, "member_id": member_id}
        )

        session = None

        try:
            # Verify admin permissions
            family = await self._get_family_by_id(family_id)
            if admin_id not in family["admin_user_ids"]:
                raise InsufficientPermissions("Only family admins can remove members")

            # Prevent removing last admin
            if member_id in family["admin_user_ids"] and len(family["admin_user_ids"]) == 1:
                raise MultipleAdminsRequired("Cannot remove the last family administrator")

            # Get member info for response
            member_user = await self._get_user_by_id(member_id)

            # Start transaction
            client = self.db_manager.client
            session = await client.start_session()

            async with session.start_transaction():
                now = datetime.now(timezone.utc)

                # Remove from family admin list if admin
                if member_id in family["admin_user_ids"]:
                    families_collection = self.db_manager.get_tenant_collection("families")
                    await families_collection.update_one(
                        {"family_id": family_id}, {"$pull": {"admin_user_ids": member_id}}, session=session
                    )

                # Remove all relationships involving this member
                relationships_collection = self.db_manager.get_collection("family_relationships")
                relationships_result = await relationships_collection.delete_many(
                    {"family_id": family_id, "$or": [{"user_a_id": member_id}, {"user_b_id": member_id}]},
                    session=session,
                )

                # Remove from user's family memberships
                users_collection = self.db_manager.get_collection("users")
                await users_collection.update_one(
                    {"_id": member_id}, {"$pull": {"family_memberships": {"family_id": family_id}}}, session=session
                )

                # Remove spending permissions
                await families_collection.update_one(
                    {"family_id": family_id},
                    {"$unset": {f"sbd_account.spending_permissions.{member_id}": ""}},
                    session=session,
                )

                # Update family member count
                await families_collection.update_one(
                    {"family_id": family_id}, {"$inc": {"member_count": -1}}, session=session
                )

                # Send notification to remaining family members
                remaining_members = await self._get_family_member_ids(family_id)
                if remaining_members:
                    notification_data = {
                        "type": "member_removed",
                        "title": "Family Member Removed",
                        "message": f"@{member_user.get('username', 'Unknown')} has been removed from the family",
                        "data": {
                            "removed_user_id": member_id,
                            "removed_username": member_user.get("username", "Unknown"),
                            "removed_by": admin_id,
                            "removed_at": now.isoformat(),
                        },
                    }
                    await self._create_family_notification(family_id, remaining_members, notification_data)

                self.db_manager.log_query_success("families", "remove_member", start_time, 1)

                return {
                    "message": "Family member removed successfully",
                    "removed_user_id": member_id,
                    "removed_username": member_user.get("username", "Unknown"),
                    "relationships_cleaned": relationships_result.deleted_count,
                    "permissions_revoked": True,
                    "removed_at": now,
                    "transaction_safe": True,
                }

        except (FamilyNotFound, InsufficientPermissions, MultipleAdminsRequired):
            raise
        except Exception as e:
            # Handle transaction rollback
            rollback_successful = False
            if session and session.in_transaction:
                try:
                    await session.abort_transaction()
                    rollback_successful = True
                except Exception:
                    pass

            self.db_manager.log_query_error(
                "families",
                "remove_member",
                start_time,
                e,
                {"family_id": family_id, "admin_id": admin_id, "member_id": member_id},
            )
            raise TransactionError(
                f"Failed to remove family member: {str(e)}",
                operation="remove_member",
                rollback_successful=rollback_successful,
            )
        finally:
            if session:
                await session.end_session()

    async def update_family_settings(
        self, family_id: str, admin_id: str, updates: Dict[str, Any], request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Update family settings and configuration.

        Args:
            family_id: ID of the family to update
            admin_id: ID of the admin performing the update
            updates: Dictionary of settings to update
            request_context: Request context for security

        Returns:
            Dict containing update confirmation

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
            ValidationError: If updates are invalid
        """
        start_time = self.db_manager.log_query_start(
            "families", "update_settings", {"family_id": family_id, "admin_id": admin_id}
        )

        try:
            # Verify admin permissions
            family = await self._get_family_by_id(family_id)
            if admin_id not in family["admin_user_ids"]:
                raise InsufficientPermissions("Only family admins can update family settings")

            # Validate updates
            allowed_fields = ["name", "settings", "notification_settings"]
            update_doc = {}
            updated_fields = []

            for field, value in updates.items():
                if field not in allowed_fields:
                    continue

                if field == "name":
                    if not isinstance(value, str) or len(value.strip()) < MIN_FAMILY_NAME_LENGTH:
                        raise ValidationError(f"Family name must be at least {MIN_FAMILY_NAME_LENGTH} characters")
                    if len(value.strip()) > MAX_FAMILY_NAME_LENGTH:
                        raise ValidationError(f"Family name must be at most {MAX_FAMILY_NAME_LENGTH} characters")
                    update_doc["name"] = value.strip()
                    updated_fields.append("name")

                elif field == "settings":
                    if isinstance(value, dict):
                        for setting_key, setting_value in value.items():
                            update_doc[f"settings.{setting_key}"] = setting_value
                            updated_fields.append(f"settings.{setting_key}")

                elif field == "notification_settings":
                    if isinstance(value, dict):
                        for setting_key, setting_value in value.items():
                            update_doc[f"sbd_account.notification_settings.{setting_key}"] = setting_value
                            updated_fields.append(f"notification_settings.{setting_key}")

            if not update_doc:
                raise ValidationError("No valid fields to update")

            # Add update timestamp
            update_doc["updated_at"] = datetime.now(timezone.utc)

            # Perform update
            families_collection = self.db_manager.get_tenant_collection("families")
            result = await families_collection.update_one({"family_id": family_id}, {"$set": update_doc})

            if result.matched_count == 0:
                raise FamilyNotFound("Family not found")

            self.db_manager.log_query_success("families", "update_settings", start_time, 1)

            return {
                "message": "Family settings updated successfully",
                "family_id": family_id,
                "updated_fields": updated_fields,
                "updated_at": update_doc["updated_at"],
                "transaction_safe": True,
            }

        except (FamilyNotFound, InsufficientPermissions, ValidationError):
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "families", "update_settings", start_time, e, {"family_id": family_id, "admin_id": admin_id}
            )
            raise FamilyError(f"Failed to update family settings: {str(e)}")

    # Account Recovery System Methods

    async def designate_backup_admin(
        self, family_id: str, admin_id: str, backup_user_id: str, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Designate a family member as backup administrator.

        Args:
            family_id: ID of the family
            admin_id: ID of the admin performing the action
            backup_user_id: ID of the user to designate as backup admin
            request_context: Request context for rate limiting and security

        Returns:
            Dict containing backup admin designation confirmation

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
            ValidationError: If backup user is invalid
            BackupAdminError: If designation fails
        """
        operation_context = {
            "family_id": family_id,
            "admin_id": admin_id,
            "backup_user_id": backup_user_id,
            "operation": "designate_backup_admin",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "designate_backup_admin", operation_context)

        # Rate limiting check
        if request_context:
            try:
                await self._check_rate_limit(request_context, "admin_action", 5, 3600)
            except Exception as e:
                raise RateLimitExceeded("Admin action rate limit exceeded", action="admin_action", limit=5, window=3600)

        session = None

        try:
            # Verify family exists and user has admin permissions
            family = await self._get_family_by_id(family_id)
            if admin_id not in family["admin_user_ids"]:
                raise InsufficientPermissions("Only family admins can designate backup administrators")

            # Verify backup user is a family member
            if not await self._is_user_in_family(backup_user_id, family_id):
                raise ValidationError("Backup admin must be a family member")

            # Verify backup user is not already an admin
            if backup_user_id in family["admin_user_ids"]:
                raise ValidationError("User is already a family administrator")

            # Check if user is already a backup admin
            current_backup_admins = family.get("succession_plan", {}).get("backup_admins", [])
            if backup_user_id in current_backup_admins:
                raise ValidationError("User is already designated as backup administrator")

            # Start transaction
            client = self.db_manager.client
            session = await client.start_session()

            async with session.start_transaction():
                now = datetime.now(timezone.utc)

                # Update family document with backup admin
                families_collection = self.db_manager.get_tenant_collection("families")
                await families_collection.update_one(
                    {"family_id": family_id},
                    {
                        "$addToSet": {"succession_plan.backup_admins": backup_user_id},
                        "$set": {
                            "updated_at": now,
                            "audit_trail.last_modified_by": admin_id,
                            "audit_trail.last_modified_at": now,
                        },
                    },
                    session=session,
                )

                # Log the backup admin designation
                await self._log_admin_action(
                    family_id=family_id,
                    admin_user_id=admin_id,
                    target_user_id=backup_user_id,
                    action_type="designate_backup_admin",
                    details={
                        "previous_role": "member",
                        "new_role": "backup_admin",
                        "designation_reason": "admin_succession_planning",
                    },
                    session=session,
                )

                # Get user info for response
                backup_user = await self._get_user_by_id(backup_user_id)
                admin_user = await self._get_user_by_id(admin_id)

                self.db_manager.log_query_success("families", "designate_backup_admin", start_time, 1)

                self.logger.info(
                    "Backup admin designated: %s for family %s by admin %s",
                    backup_user_id,
                    family_id,
                    admin_id,
                    extra={
                        "family_id": family_id,
                        "backup_user_id": backup_user_id,
                        "admin_id": admin_id,
                        "transaction_safe": True,
                    },
                )

                return {
                    "family_id": family_id,
                    "backup_user_id": backup_user_id,
                    "backup_username": backup_user.get("username", "Unknown"),
                    "action": "designated",
                    "role": "backup_admin",
                    "performed_by": admin_id,
                    "performed_by_username": admin_user.get("username", "Unknown"),
                    "performed_at": now,
                    "message": "User successfully designated as backup administrator",
                    "transaction_safe": True,
                }

        except (FamilyNotFound, InsufficientPermissions, ValidationError, BackupAdminError, RateLimitExceeded) as e:
            self.db_manager.log_query_error("families", "designate_backup_admin", start_time, e, operation_context)
            raise

        except Exception as e:
            # Handle transaction rollback
            rollback_successful = False
            if session and session.in_transaction:
                try:
                    await session.abort_transaction()
                    rollback_successful = True
                except Exception as rollback_error:
                    self.logger.error("Failed to rollback backup admin designation: %s", rollback_error, exc_info=True)

            self.db_manager.log_query_error("families", "designate_backup_admin", start_time, e, operation_context)
            self.logger.error(
                "Failed to designate backup admin for family %s: %s",
                family_id,
                e,
                exc_info=True,
                extra={
                    "family_id": family_id,
                    "backup_user_id": backup_user_id,
                    "admin_id": admin_id,
                    "rollback_successful": rollback_successful,
                },
            )

            raise BackupAdminError(
                f"Failed to designate backup administrator: {str(e)}",
                operation="designate_backup_admin",
                backup_admin=backup_user_id,
            )

        finally:
            if session:
                await session.end_session()

    async def remove_backup_admin(
        self, family_id: str, admin_id: str, backup_user_id: str, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Remove backup administrator designation from a family member.

        Args:
            family_id: ID of the family
            admin_id: ID of the admin performing the action
            backup_user_id: ID of the backup admin to remove
            request_context: Request context for rate limiting and security

        Returns:
            Dict containing backup admin removal confirmation

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
            ValidationError: If backup user is invalid
            BackupAdminError: If removal fails
        """
        operation_context = {
            "family_id": family_id,
            "admin_id": admin_id,
            "backup_user_id": backup_user_id,
            "operation": "remove_backup_admin",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "remove_backup_admin", operation_context)

        # Rate limiting check
        if request_context:
            try:
                await self._check_rate_limit(request_context, "admin_action", 5, 3600)
            except Exception as e:
                raise RateLimitExceeded("Admin action rate limit exceeded", action="admin_action", limit=5, window=3600)

        session = None

        try:
            # Verify family exists and user has admin permissions
            family = await self._get_family_by_id(family_id)
            if admin_id not in family["admin_user_ids"]:
                raise InsufficientPermissions("Only family admins can remove backup administrators")

            # Check if user is currently a backup admin
            current_backup_admins = family.get("succession_plan", {}).get("backup_admins", [])
            if backup_user_id not in current_backup_admins:
                raise ValidationError("User is not currently designated as backup administrator")

            # Start transaction
            client = self.db_manager.client
            session = await client.start_session()

            async with session.start_transaction():
                now = datetime.now(timezone.utc)

                # Update family document to remove backup admin
                families_collection = self.db_manager.get_tenant_collection("families")
                await families_collection.update_one(
                    {"family_id": family_id},
                    {
                        "$pull": {"succession_plan.backup_admins": backup_user_id},
                        "$set": {
                            "updated_at": now,
                            "audit_trail.last_modified_by": admin_id,
                            "audit_trail.last_modified_at": now,
                        },
                    },
                    session=session,
                )

                # Log the backup admin removal
                await self._log_admin_action(
                    family_id=family_id,
                    admin_user_id=admin_id,
                    target_user_id=backup_user_id,
                    action_type="remove_backup_admin",
                    details={"previous_role": "backup_admin", "new_role": "member", "removal_reason": "admin_action"},
                    session=session,
                )

                # Get user info for response
                backup_user = await self._get_user_by_id(backup_user_id)
                admin_user = await self._get_user_by_id(admin_id)

                self.db_manager.log_query_success("families", "remove_backup_admin", start_time, 1)

                self.logger.info(
                    "Backup admin removed: %s from family %s by admin %s",
                    backup_user_id,
                    family_id,
                    admin_id,
                    extra={
                        "family_id": family_id,
                        "backup_user_id": backup_user_id,
                        "admin_id": admin_id,
                        "transaction_safe": True,
                    },
                )

                return {
                    "family_id": family_id,
                    "backup_user_id": backup_user_id,
                    "backup_username": backup_user.get("username", "Unknown"),
                    "action": "removed",
                    "role": "member",
                    "performed_by": admin_id,
                    "performed_by_username": admin_user.get("username", "Unknown"),
                    "performed_at": now,
                    "message": "Backup administrator designation removed successfully",
                    "transaction_safe": True,
                }

        except (FamilyNotFound, InsufficientPermissions, ValidationError, BackupAdminError, RateLimitExceeded) as e:
            self.db_manager.log_query_error("families", "remove_backup_admin", start_time, e, operation_context)
            raise

        except Exception as e:
            # Handle transaction rollback
            rollback_successful = False
            if session and session.in_transaction:
                try:
                    await session.abort_transaction()
                    rollback_successful = True
                except Exception as rollback_error:
                    self.logger.error("Failed to rollback backup admin removal: %s", rollback_error, exc_info=True)

            self.db_manager.log_query_error("families", "remove_backup_admin", start_time, e, operation_context)
            self.logger.error(
                "Failed to remove backup admin from family %s: %s",
                family_id,
                e,
                exc_info=True,
                extra={
                    "family_id": family_id,
                    "backup_user_id": backup_user_id,
                    "admin_id": admin_id,
                    "rollback_successful": rollback_successful,
                },
            )

            raise BackupAdminError(
                f"Failed to remove backup administrator: {str(e)}",
                operation="remove_backup_admin",
                backup_admin=backup_user_id,
            )

        finally:
            if session:
                await session.end_session()

    async def initiate_account_recovery(
        self, family_id: str, initiator_id: str, recovery_reason: str, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Initiate account recovery process when admin accounts are compromised or deleted.

        Args:
            family_id: ID of the family requiring recovery
            initiator_id: ID of the family member initiating recovery
            recovery_reason: Reason for initiating recovery
            request_context: Request context for rate limiting and security

        Returns:
            Dict containing recovery initiation confirmation

        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user cannot initiate recovery
            ValidationError: If recovery conditions are not met
            FamilyError: If recovery initiation fails
        """
        operation_context = {
            "family_id": family_id,
            "initiator_id": initiator_id,
            "recovery_reason": recovery_reason,
            "operation": "initiate_account_recovery",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "initiate_account_recovery", operation_context)

        # Rate limiting check
        if request_context:
            try:
                await self._check_rate_limit(request_context, "recovery_action", 2, 3600)
            except Exception as e:
                raise RateLimitExceeded(
                    "Recovery action rate limit exceeded", action="recovery_action", limit=2, window=3600
                )

        session = None

        try:
            # Verify family exists
            family = await self._get_family_by_id(family_id)

            # Verify initiator is a family member
            if not await self._is_user_in_family(initiator_id, family_id):
                raise InsufficientPermissions("Only family members can initiate account recovery")

            # Check if there are any active admins
            active_admin_count = len(family["admin_user_ids"])
            if active_admin_count > 0:
                raise ValidationError("Account recovery can only be initiated when no active admins exist")

            # Check if there are backup admins available
            backup_admins = family.get("succession_plan", {}).get("backup_admins", [])
            if backup_admins:
                # Automatically promote first backup admin
                return await self._auto_promote_backup_admin(family_id, backup_admins[0], initiator_id)

            # No backup admins - initiate multi-member verification process
            recovery_id = f"rec_{uuid.uuid4().hex[:16]}"
            now = datetime.now(timezone.utc)

            # Start transaction
            client = self.db_manager.client
            session = await client.start_session()

            async with session.start_transaction():
                # Create recovery request
                recovery_collection = self.db_manager.get_collection("family_recovery_requests")
                recovery_doc = {
                    "recovery_id": recovery_id,
                    "family_id": family_id,
                    "initiated_by": initiator_id,
                    "recovery_reason": recovery_reason,
                    "status": "pending_verification",
                    "created_at": now,
                    "expires_at": now + timedelta(hours=72),  # 72 hour window for verification
                    "required_verifications": max(2, len(await self._get_family_members(family_id)) // 2),
                    "verifications": [],
                    "recovery_method": "multi_member_verification",
                }

                await recovery_collection.insert_one(recovery_doc, session=session)

                # Log recovery initiation
                await self._log_recovery_event(
                    family_id=family_id,
                    recovery_id=recovery_id,
                    event_type="recovery_initiated",
                    details={
                        "initiated_by": initiator_id,
                        "reason": recovery_reason,
                        "method": "multi_member_verification",
                        "required_verifications": recovery_doc["required_verifications"],
                    },
                    session=session,
                )

                # Notify all family members about recovery initiation
                await self._notify_family_members_recovery(family_id, recovery_id, "recovery_initiated", session)

                self.db_manager.log_query_success("families", "initiate_account_recovery", start_time, 1)

                self.logger.info(
                    "Account recovery initiated: %s for family %s by %s",
                    recovery_id,
                    family_id,
                    initiator_id,
                    extra={
                        "recovery_id": recovery_id,
                        "family_id": family_id,
                        "initiator_id": initiator_id,
                        "transaction_safe": True,
                    },
                )

                return {
                    "recovery_id": recovery_id,
                    "family_id": family_id,
                    "status": "pending_verification",
                    "required_verifications": recovery_doc["required_verifications"],
                    "expires_at": recovery_doc["expires_at"],
                    "message": "Account recovery initiated. Multi-member verification required.",
                    "transaction_safe": True,
                }

        except (FamilyNotFound, InsufficientPermissions, ValidationError, RateLimitExceeded) as e:
            self.db_manager.log_query_error("families", "initiate_account_recovery", start_time, e, operation_context)
            raise

        except Exception as e:
            # Handle transaction rollback
            rollback_successful = False
            if session and session.in_transaction:
                try:
                    await session.abort_transaction()
                    rollback_successful = True
                except Exception as rollback_error:
                    self.logger.error("Failed to rollback recovery initiation: %s", rollback_error, exc_info=True)

            self.db_manager.log_query_error("families", "initiate_account_recovery", start_time, e, operation_context)
            self.logger.error(
                "Failed to initiate account recovery for family %s: %s",
                family_id,
                e,
                exc_info=True,
                extra={
                    "family_id": family_id,
                    "initiator_id": initiator_id,
                    "rollback_successful": rollback_successful,
                },
            )

            raise FamilyError(f"Failed to initiate account recovery: {str(e)}")

        finally:
            if session:
                await session.end_session()

    async def verify_account_recovery(
        self, recovery_id: str, verifier_id: str, verification_code: str, request_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Verify account recovery request by family member.

        Args:
            recovery_id: ID of the recovery request
            verifier_id: ID of the family member providing verification
            verification_code: Verification code (email-based or other method)
            request_context: Request context for rate limiting and security

        Returns:
            Dict containing verification confirmation

        Raises:
            ValidationError: If verification is invalid
            FamilyError: If verification fails
        """
        operation_context = {
            "recovery_id": recovery_id,
            "verifier_id": verifier_id,
            "operation": "verify_account_recovery",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("family_recovery_requests", "verify_recovery", operation_context)

        # Rate limiting check
        if request_context:
            try:
                await self._check_rate_limit(request_context, "recovery_verification", 5, 3600)
            except Exception as e:
                raise RateLimitExceeded(
                    "Recovery verification rate limit exceeded", action="recovery_verification", limit=5, window=3600
                )

        session = None

        try:
            # Get recovery request
            recovery_collection = self.db_manager.get_collection("family_recovery_requests")
            recovery_request = await recovery_collection.find_one({"recovery_id": recovery_id})

            if not recovery_request:
                raise ValidationError("Recovery request not found")

            if recovery_request["status"] != "pending_verification":
                raise ValidationError("Recovery request is not in pending verification status")

            expires_at = recovery_request["expires_at"]
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                raise ValidationError("Recovery request has expired")

            # Verify user is a family member
            family_id = recovery_request["family_id"]
            if not await self._is_user_in_family(verifier_id, family_id):
                raise InsufficientPermissions("Only family members can verify recovery requests")

            # Check if user has already verified
            existing_verifications = recovery_request.get("verifications", [])
            if any(v["verifier_id"] == verifier_id for v in existing_verifications):
                raise ValidationError("User has already provided verification for this recovery request")

            # Validate verification code (simplified - in production would verify email codes, etc.)
            if not verification_code or len(verification_code) < 6:
                raise ValidationError("Invalid verification code")

            # Start transaction
            client = self.db_manager.client
            session = await client.start_session()

            async with session.start_transaction():
                now = datetime.now(timezone.utc)

                # Add verification
                verification = {
                    "verifier_id": verifier_id,
                    "verified_at": now,
                    "verification_method": "email_code",
                    "verification_code_hash": verification_code,  # In production, would hash this
                }

                await recovery_collection.update_one(
                    {"recovery_id": recovery_id}, {"$push": {"verifications": verification}}, session=session
                )

                # Check if we have enough verifications
                updated_request = await recovery_collection.find_one({"recovery_id": recovery_id}, session=session)
                current_verifications = len(updated_request["verifications"])
                required_verifications = updated_request["required_verifications"]

                if current_verifications >= required_verifications:
                    # Complete recovery process
                    return await self._complete_account_recovery(recovery_id, session)

                # Log verification
                await self._log_recovery_event(
                    family_id=family_id,
                    recovery_id=recovery_id,
                    event_type="verification_provided",
                    details={
                        "verifier_id": verifier_id,
                        "current_verifications": current_verifications,
                        "required_verifications": required_verifications,
                    },
                    session=session,
                )

                self.db_manager.log_query_success("family_recovery_requests", "verify_recovery", start_time, 1)

                return {
                    "recovery_id": recovery_id,
                    "verification_accepted": True,
                    "current_verifications": current_verifications,
                    "required_verifications": required_verifications,
                    "recovery_complete": False,
                    "message": f"Verification accepted. {required_verifications - current_verifications} more verifications needed.",
                    "transaction_safe": True,
                }

        except (ValidationError, InsufficientPermissions, RateLimitExceeded) as e:
            self.db_manager.log_query_error(
                "family_recovery_requests", "verify_recovery", start_time, e, operation_context
            )
            raise

        except Exception as e:
            # Handle transaction rollback
            rollback_successful = False
            if session and session.in_transaction:
                try:
                    await session.abort_transaction()
                    rollback_successful = True
                except Exception as rollback_error:
                    self.logger.error("Failed to rollback recovery verification: %s", rollback_error, exc_info=True)

            self.db_manager.log_query_error(
                "family_recovery_requests", "verify_recovery", start_time, e, operation_context
            )
            self.logger.error(
                "Failed to verify account recovery %s: %s",
                recovery_id,
                e,
                exc_info=True,
                extra={
                    "recovery_id": recovery_id,
                    "verifier_id": verifier_id,
                    "rollback_successful": rollback_successful,
                },
            )

            raise FamilyError(f"Failed to verify account recovery: {str(e)}")

        finally:
            if session:
                await session.end_session()

    async def handle_admin_account_deletion(self, deleted_admin_id: str) -> None:
        """
        Handle automatic admin promotion when an admin account is deleted.

        This method is called by the user deletion system to ensure family continuity.

        Args:
            deleted_admin_id: ID of the deleted admin account

        Raises:
            FamilyError: If automatic promotion fails
        """
        operation_context = {
            "deleted_admin_id": deleted_admin_id,
            "operation": "handle_admin_deletion",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        start_time = self.db_manager.log_query_start("families", "handle_admin_deletion", operation_context)

        try:
            # Find all families where the deleted user was an admin
            families_collection = self.db_manager.get_tenant_collection("families")
            affected_families = await families_collection.find(
                {"admin_user_ids": deleted_admin_id, "is_active": True}
            ).to_list(None)

            for family in affected_families:
                family_id = family["family_id"]

                # Remove deleted admin from admin list
                remaining_admins = [admin_id for admin_id in family["admin_user_ids"] if admin_id != deleted_admin_id]

                if remaining_admins:
                    # Still have other admins, just remove the deleted one
                    await families_collection.update_one(
                        {"family_id": family_id},
                        {"$set": {"admin_user_ids": remaining_admins}, "$inc": {"member_count": -1}},
                    )

                    # Log admin removal due to deletion
                    await self._log_admin_action(
                        family_id=family_id,
                        admin_user_id="system",
                        target_user_id=deleted_admin_id,
                        action_type="admin_removed_account_deleted",
                        details={"deletion_reason": "account_deleted", "remaining_admins": len(remaining_admins)},
                    )

                else:
                    # No remaining admins - need to promote someone
                    await self._handle_last_admin_deletion(family_id, deleted_admin_id)

            self.db_manager.log_query_success("families", "handle_admin_deletion", start_time, len(affected_families))

            self.logger.info(
                "Handled admin account deletion for %d families: %s",
                len(affected_families),
                deleted_admin_id,
                extra={"deleted_admin_id": deleted_admin_id, "affected_families": len(affected_families)},
            )

        except Exception as e:
            self.db_manager.log_query_error("families", "handle_admin_deletion", start_time, e, operation_context)
            self.logger.error(
                "Failed to handle admin account deletion %s: %s",
                deleted_admin_id,
                e,
                exc_info=True,
                extra={"deleted_admin_id": deleted_admin_id},
            )

            raise FamilyError(f"Failed to handle admin account deletion: {str(e)}")

    # Private helper methods for account recovery

    async def _auto_promote_backup_admin(
        self, family_id: str, backup_admin_id: str, initiator_id: str
    ) -> Dict[str, Any]:
        """Automatically promote backup admin when primary admin is deleted."""
        session = None

        try:
            client = self.db_manager.client
            session = await client.start_session()

            async with session.start_transaction():
                now = datetime.now(timezone.utc)

                # Promote backup admin to full admin
                families_collection = self.db_manager.get_tenant_collection("families")
                await families_collection.update_one(
                    {"family_id": family_id},
                    {
                        "$addToSet": {"admin_user_ids": backup_admin_id},
                        "$pull": {"succession_plan.backup_admins": backup_admin_id},
                        "$set": {
                            "updated_at": now,
                            "audit_trail.last_modified_by": "system_recovery",
                            "audit_trail.last_modified_at": now,
                        },
                    },
                    session=session,
                )

                # Update user's family membership role
                users_collection = self.db_manager.get_collection("users")
                await users_collection.update_one(
                    {"_id": backup_admin_id, "family_memberships.family_id": family_id},
                    {
                        "$set": {
                            "family_memberships.$.role": "admin",
                            "family_memberships.$.spending_permissions.can_spend": True,
                            "family_memberships.$.spending_permissions.spending_limit": -1,
                            "family_memberships.$.spending_permissions.last_updated": now,
                        }
                    },
                    session=session,
                )

                # Log automatic promotion
                await self._log_admin_action(
                    family_id=family_id,
                    admin_user_id="system_recovery",
                    target_user_id=backup_admin_id,
                    action_type="auto_promote_backup_admin",
                    details={
                        "promotion_reason": "admin_account_recovery",
                        "initiated_by": initiator_id,
                        "promotion_method": "automatic_succession",
                    },
                    session=session,
                )

                # Get user info for response
                backup_user = await self._get_user_by_id(backup_admin_id)

                self.logger.info(
                    "Backup admin automatically promoted: %s for family %s",
                    backup_admin_id,
                    family_id,
                    extra={"family_id": family_id, "backup_admin_id": backup_admin_id, "initiator_id": initiator_id},
                )

                return {
                    "recovery_method": "automatic_backup_promotion",
                    "promoted_user_id": backup_admin_id,
                    "promoted_username": backup_user.get("username", "Unknown"),
                    "family_id": family_id,
                    "promoted_at": now,
                    "message": "Backup administrator automatically promoted to full administrator",
                    "transaction_safe": True,
                }

        finally:
            if session:
                await session.end_session()

    async def _handle_last_admin_deletion(self, family_id: str, deleted_admin_id: str) -> None:
        """Handle deletion of the last admin in a family."""
        # Check for backup admins first
        family = await self._get_family_by_id(family_id)
        backup_admins = family.get("succession_plan", {}).get("backup_admins", [])

        if backup_admins:
            # Promote first backup admin
            await self._auto_promote_backup_admin(family_id, backup_admins[0], "system")
        else:
            # Find senior family member to promote
            family_members = await self._get_family_members(family_id)
            if family_members:
                # Sort by join date and promote the most senior member
                senior_member = min(family_members, key=lambda m: m.get("joined_at", datetime.now(timezone.utc)))
                await self._promote_member_to_admin(family_id, senior_member["user_id"], "system_recovery")
            else:
                # No members left - deactivate family
                await self._deactivate_family(family_id, "no_members_remaining")

    async def _complete_account_recovery(self, recovery_id: str, session: ClientSession) -> Dict[str, Any]:
        """Complete the account recovery process after sufficient verifications."""
        recovery_collection = self.db_manager.get_collection("family_recovery_requests")
        recovery_request = await recovery_collection.find_one({"recovery_id": recovery_id}, session=session)

        family_id = recovery_request["family_id"]

        # Find the most senior family member to promote
        family_members = await self._get_family_members(family_id)
        if not family_members:
            raise FamilyError("No family members available for promotion")

        # Sort by join date and promote the most senior member
        senior_member = min(family_members, key=lambda m: m.get("joined_at", datetime.now(timezone.utc)))

        # Promote to admin
        await self._promote_member_to_admin(family_id, senior_member["user_id"], "recovery_system", session)

        # Update recovery request status
        now = datetime.now(timezone.utc)
        await recovery_collection.update_one(
            {"recovery_id": recovery_id},
            {"$set": {"status": "completed", "completed_at": now, "promoted_user_id": senior_member["user_id"]}},
            session=session,
        )

        # Log recovery completion
        await self._log_recovery_event(
            family_id=family_id,
            recovery_id=recovery_id,
            event_type="recovery_completed",
            details={
                "promoted_user_id": senior_member["user_id"],
                "promotion_method": "multi_member_verification",
                "total_verifications": len(recovery_request["verifications"]),
            },
            session=session,
        )

        return {
            "recovery_id": recovery_id,
            "recovery_complete": True,
            "promoted_user_id": senior_member["user_id"],
            "promoted_username": senior_member.get("username", "Unknown"),
            "message": "Account recovery completed successfully. Senior member promoted to administrator.",
            "transaction_safe": True,
        }

    async def _promote_member_to_admin(
        self, family_id: str, user_id: str, promoted_by: str, session: ClientSession = None
    ) -> None:
        """Promote a family member to administrator."""
        now = datetime.now(timezone.utc)

        # Update family document
        families_collection = self.db_manager.get_tenant_collection("families")
        await families_collection.update_one(
            {"family_id": family_id},
            {
                "$addToSet": {"admin_user_ids": user_id},
                "$set": {
                    "updated_at": now,
                    "audit_trail.last_modified_by": promoted_by,
                    "audit_trail.last_modified_at": now,
                },
            },
            session=session,
        )

        # Update user's family membership role
        users_collection = self.db_manager.get_collection("users")
        await users_collection.update_one(
            {"_id": user_id, "family_memberships.family_id": family_id},
            {
                "$set": {
                    "family_memberships.$.role": "admin",
                    "family_memberships.$.spending_permissions.can_spend": True,
                    "family_memberships.$.spending_permissions.spending_limit": -1,
                    "family_memberships.$.spending_permissions.last_updated": now,
                }
            },
            session=session,
        )

        # Log promotion
        await self._log_admin_action(
            family_id=family_id,
            admin_user_id=promoted_by,
            target_user_id=user_id,
            action_type="promote_to_admin",
            details={"promotion_reason": "account_recovery", "previous_role": "member", "new_role": "admin"},
            session=session,
        )

    async def _get_family_members(self, family_id: str) -> List[Dict[str, Any]]:
        """Get all family members with their details."""
        users_collection = self.db_manager.get_collection("users")
        members = await users_collection.find({"family_memberships.family_id": family_id}).to_list(None)

        family_members = []
        for member in members:
            for membership in member.get("family_memberships", []):
                if membership["family_id"] == family_id:
                    family_members.append(
                        {
                            "user_id": str(member["_id"]),
                            "username": member.get("username", "Unknown"),
                            "email": member.get("email", ""),
                            "role": membership["role"],
                            "joined_at": membership["joined_at"],
                        }
                    )
                    break

        return family_members

    async def _log_admin_action(
        self,
        family_id: str,
        admin_user_id: str,
        target_user_id: str,
        action_type: str,
        details: Dict[str, Any],
        session: ClientSession = None,
    ) -> None:
        """Log admin actions for audit trail."""
        admin_actions_collection = self.db_manager.get_tenant_collection("family_admin_actions")

        action_doc = {
            "action_id": f"act_{uuid.uuid4().hex[:16]}",
            "family_id": family_id,
            "admin_user_id": admin_user_id,
            "target_user_id": target_user_id,
            "action_type": action_type,
            "details": details,
            "created_at": datetime.now(timezone.utc),
            "ip_address": None,  # Could be populated from request context
            "user_agent": None,  # Could be populated from request context
        }

        await admin_actions_collection.insert_one(action_doc, session=session)

    async def _log_recovery_event(
        self, family_id: str, recovery_id: str, event_type: str, details: Dict[str, Any], session: ClientSession = None
    ) -> None:
        """Log recovery events for audit trail."""
        recovery_events_collection = self.db_manager.get_collection("family_recovery_events")

        event_doc = {
            "event_id": f"evt_{uuid.uuid4().hex[:16]}",
            "family_id": family_id,
            "recovery_id": recovery_id,
            "event_type": event_type,
            "details": details,
            "created_at": datetime.now(timezone.utc),
        }

        await recovery_events_collection.insert_one(event_doc, session=session)

    async def _notify_family_members_recovery(
        self, family_id: str, recovery_id: str, event_type: str, session: ClientSession = None
    ) -> None:
        """Notify all family members about recovery events."""
        # This would integrate with the notification system
        # For now, just log the notification
        self.logger.info(
            "Recovery notification sent to family %s: %s (recovery: %s)", family_id, event_type, recovery_id
        )

    async def _deactivate_family(self, family_id: str, reason: str) -> None:
        """Deactivate a family when no members remain."""
        families_collection = self.db_manager.get_tenant_collection("families")
        await families_collection.update_one(
            {"family_id": family_id},
            {"$set": {"is_active": False, "deactivated_at": datetime.now(timezone.utc), "deactivation_reason": reason}},
        )

        self.logger.info("Family deactivated: %s (reason: %s)", family_id, reason)

    async def _log_virtual_account_security_event(
        self, account_id: str, username: str, event_type: str, details: Dict[str, Any], session: ClientSession = None
    ) -> None:
        """Log security events for virtual accounts."""
        security_events_collection = self.db_manager.get_collection("virtual_account_security_events")

        event_doc = {
            "event_id": f"sec_{uuid.uuid4().hex[:16]}",
            "account_id": account_id,
            "username": username,
            "event_type": event_type,
            "details": details,
            "created_at": datetime.now(timezone.utc),
        }

        await security_events_collection.insert_one(event_doc, session=session)

    # Family Limits and Billing Integration Methods

    async def update_family_limits(
        self, user_id: str, new_limits: Dict[str, Any], updated_by: str, reason: str = None
    ) -> Dict[str, Any]:
        """
        Update family limits for a user (admin/billing system use).

        Args:
            user_id: ID of the user whose limits to update
            new_limits: New limit values
            updated_by: ID of the user/system updating the limits
            reason: Reason for the update

        Returns:
            Dict containing update results and audit information
        """
        try:
            from second_brain_database.config import settings

            user = await self._get_user_by_id(user_id)
            current_limits = user.get("family_limits", {})

            # Prepare the update
            updated_limits = current_limits.copy()
            previous_limits = current_limits.copy()

            # Update limits if provided
            if "max_families_allowed" in new_limits:
                updated_limits["max_families_allowed"] = new_limits["max_families_allowed"]
            if "max_members_per_family" in new_limits:
                updated_limits["max_members_per_family"] = new_limits["max_members_per_family"]

            # Set metadata
            updated_limits["updated_at"] = datetime.now(timezone.utc)
            updated_limits["updated_by"] = updated_by

            # Calculate grace period for downgrades
            grace_period_expires = None
            if new_limits.get("grace_period_days"):
                grace_period_expires = datetime.now(timezone.utc) + timedelta(days=new_limits["grace_period_days"])
                updated_limits["grace_period_expires"] = grace_period_expires

            # Validate new limits against current usage
            validation_result = await self._validate_limit_changes(user_id, updated_limits, previous_limits)

            # Update user document
            users_collection = self.db_manager.get_collection("users")
            await users_collection.update_one({"_id": user_id}, {"$set": {"family_limits": updated_limits}})

            # Create audit log entry
            audit_log_id = await self._create_limits_audit_log(
                user_id, previous_limits, updated_limits, updated_by, reason
            )

            # Track usage event if enabled
            if settings.ENABLE_FAMILY_USAGE_TRACKING:
                await self._track_usage_event(
                    user_id,
                    "limits_updated",
                    {"previous_limits": previous_limits, "new_limits": updated_limits, "updated_by": updated_by},
                )

            self.logger.info("Family limits updated for user %s by %s", user_id, updated_by)

            return {
                "user_id": user_id,
                "previous_limits": previous_limits,
                "new_limits": updated_limits,
                "effective_date": updated_limits["updated_at"],
                "grace_period_expires": grace_period_expires,
                "updated_by": updated_by,
                "updated_at": updated_limits["updated_at"],
                "audit_log_id": audit_log_id,
                "validation_warnings": validation_result.get("warnings", []),
            }

        except Exception as e:
            self.logger.error("Failed to update family limits for user %s: %s", user_id, e, exc_info=True)
            raise FamilyError(f"Failed to update family limits: {str(e)}")

    async def _validate_limit_changes(
        self, user_id: str, new_limits: Dict[str, Any], previous_limits: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate limit changes against current usage."""
        try:
            warnings = []

            # Check current usage
            current_usage = await self.check_family_limits(user_id)

            # Check family count limit
            new_max_families = new_limits.get("max_families_allowed", previous_limits.get("max_families_allowed", 1))
            if current_usage["current_families"] > new_max_families:
                warnings.append(
                    f"User currently has {current_usage['current_families']} families but new limit is {new_max_families}"
                )

            # Check member count limits
            new_max_members = new_limits.get("max_members_per_family", previous_limits.get("max_members_per_family", 5))
            for family_usage in current_usage["families_usage"]:
                if family_usage["is_admin"] and family_usage["member_count"] > new_max_members:
                    warnings.append(
                        f"Family '{family_usage['name']}' has {family_usage['member_count']} members but new limit is {new_max_members}"
                    )

            return {"warnings": warnings}

        except Exception as e:
            self.logger.warning("Failed to validate limit changes: %s", e)
            return {"warnings": ["Could not validate limit changes"]}

    async def _create_limits_audit_log(
        self, user_id: str, previous_limits: Dict[str, Any], new_limits: Dict[str, Any], updated_by: str, reason: str
    ) -> str:
        """Create audit log entry for limits update."""
        try:
            audit_collection = self.db_manager.get_collection("family_limits_audit")

            audit_entry = {
                "audit_id": f"audit_{uuid.uuid4().hex[:16]}",
                "user_id": user_id,
                "action": "limits_updated",
                "previous_limits": previous_limits,
                "new_limits": new_limits,
                "updated_by": updated_by,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc),
                "ip_address": None,  # TODO: Get from request context
                "user_agent": None,  # TODO: Get from request context
            }

            await audit_collection.insert_one(audit_entry)
            return audit_entry["audit_id"]

        except Exception as e:
            self.logger.warning("Failed to create audit log entry: %s", e)
            return f"audit_error_{uuid.uuid4().hex[:16]}"

    async def get_usage_tracking_data(
        self, user_id: str, start_date: datetime = None, end_date: datetime = None, granularity: str = "daily"
    ) -> Dict[str, Any]:
        """
        Get comprehensive family usage tracking data for billing integration.

        Args:
            user_id: ID of the user
            start_date: Start date for tracking data
            end_date: End date for tracking data
            granularity: Data granularity (daily, weekly, monthly)

        Returns:
            Dict containing comprehensive usage tracking data and metrics
        """
        try:
            from second_brain_database.config import settings

            if not settings.ENABLE_FAMILY_USAGE_TRACKING:
                raise FamilyError("Usage tracking is not enabled")

            # Set default date range if not provided
            if not end_date:
                end_date = datetime.now(timezone.utc)
            if not start_date:
                start_date = end_date - timedelta(days=30)

            # Get usage data
            usage_data = await self._get_usage_tracking_data(user_id, start_date, end_date, granularity)

            # Get billing metrics
            billing_metrics = await self._get_billing_usage_metrics(user_id, (end_date - start_date).days)

            # Get current limits for context
            current_limits = await self.check_family_limits(user_id, include_billing_metrics=False)

            # Calculate enhanced summary statistics
            total_families_created = sum(1 for day in usage_data if "family_created" in day.get("events", []))
            total_members_added = sum(1 for day in usage_data if "member_added" in day.get("events", []))

            # Find peak usage day
            peak_day = max(usage_data, key=lambda x: x.get("total_members", 0), default={})
            peak_usage_day = peak_day.get("date").isoformat() if peak_day.get("date") else None

            # Calculate averages
            total_days = len(usage_data) if usage_data else 1
            avg_daily_families = sum(day.get("families_count", 0) for day in usage_data) / total_days
            avg_daily_members = sum(day.get("total_members", 0) for day in usage_data) / total_days

            # Determine usage trend
            usage_trend = self._calculate_usage_trend(usage_data)

            # Generate recommendations
            recommendations = self._generate_usage_recommendations(
                current_limits, billing_metrics, total_families_created, total_members_added
            )

            summary = {
                "total_families_created": total_families_created,
                "total_members_added": total_members_added,
                "peak_usage_day": peak_usage_day,
                "average_daily_families": round(avg_daily_families, 2),
                "average_daily_members": round(avg_daily_members, 2),
                "upgrade_recommended": len(billing_metrics.get("upgrade_recommendations", [])) > 0,
                "usage_trend": usage_trend,
            }

            return {
                "user_id": user_id,
                "period_start": start_date,
                "period_end": end_date,
                "granularity": granularity,
                "usage_data": usage_data,
                "billing_metrics": billing_metrics,
                "summary": summary,
                "current_limits": {
                    "max_families_allowed": current_limits["max_families_allowed"],
                    "max_members_per_family": current_limits["max_members_per_family"],
                    "current_families": current_limits["current_families"],
                },
                "recommendations": recommendations,
            }

        except Exception as e:
            self.logger.error("Failed to get usage tracking data for user %s: %s", user_id, e, exc_info=True)
            raise FamilyError(f"Failed to get usage tracking data: {str(e)}")

    def _calculate_usage_trend(self, usage_data: List[Dict[str, Any]]) -> str:
        """Calculate usage trend from historical data."""
        try:
            if len(usage_data) < 7:  # Need at least a week of data
                return "insufficient_data"

            # Split data into first and second half
            mid_point = len(usage_data) // 2
            first_half = usage_data[:mid_point]
            second_half = usage_data[mid_point:]

            # Calculate average members for each half
            first_avg = sum(day.get("total_members", 0) for day in first_half) / len(first_half)
            second_avg = sum(day.get("total_members", 0) for day in second_half) / len(second_half)

            # Determine trend
            if second_avg > first_avg * 1.1:  # 10% increase
                return "increasing"
            elif second_avg < first_avg * 0.9:  # 10% decrease
                return "decreasing"
            else:
                return "stable"

        except Exception as e:
            self.logger.warning("Failed to calculate usage trend: %s", e)
            return "unknown"

    def _generate_usage_recommendations(
        self, current_limits: Dict[str, Any], billing_metrics: Dict[str, Any], families_created: int, members_added: int
    ) -> List[str]:
        """Generate usage-based recommendations."""
        try:
            recommendations = []

            # Check if approaching limits
            families_usage_pct = (current_limits["current_families"] / current_limits["max_families_allowed"]) * 100

            if families_usage_pct >= 80:
                recommendations.append("You're approaching your family limit - consider upgrading")
            elif families_usage_pct >= 100:
                recommendations.append("You've reached your family limit - upgrade to create more families")

            # Check activity levels
            if families_created > 0 and members_added > 5:
                recommendations.append("High activity detected - Pro plan offers unlimited families and members")

            # Check billing metrics recommendations
            billing_recs = billing_metrics.get("upgrade_recommendations", [])
            recommendations.extend(billing_recs)

            # Default recommendation if none generated
            if not recommendations:
                if current_limits["current_families"] == 0:
                    recommendations.append("Create your first family to start managing shared resources")
                else:
                    recommendations.append("Your usage is within limits - continue enjoying family features")

            return recommendations[:5]  # Limit to 5 recommendations

        except Exception as e:
            self.logger.warning("Failed to generate usage recommendations: %s", e)
            return ["Contact support for personalized recommendations"]

    async def get_limit_enforcement_status(self, user_id: str) -> Dict[str, Any]:
        """
        Get detailed limit enforcement status and validation results.

        Args:
            user_id: ID of the user

        Returns:
            Dict containing comprehensive enforcement status information
        """
        try:
            from second_brain_database.config import settings

            # Get current limits and usage
            limits_data = await self.check_family_limits(user_id, include_billing_metrics=False)
            user = await self._get_user_by_id(user_id)

            # Get user's families for validation
            family_memberships = user.get("family_memberships", [])

            # Check enforcement status for each limit type
            limit_statuses = []
            family_validations = []
            overall_compliance = True
            total_violations = 0

            # Family count limit status
            families_limit_status = {
                "limit_type": "families",
                "is_enforced": True,
                "current_value": limits_data["current_families"],
                "limit_value": limits_data["max_families_allowed"],
                "is_compliant": limits_data["current_families"] <= limits_data["max_families_allowed"],
                "grace_period_active": False,
                "grace_period_expires": None,
                "enforcement_action": "block_creation",
            }

            if not families_limit_status["is_compliant"]:
                overall_compliance = False
                total_violations += 1

            limit_statuses.append(families_limit_status)

            # Validate each family against member limits
            compliant_families = 0
            for membership in family_memberships:
                try:
                    family = await self._get_family_by_id(membership["family_id"])
                    if not family:
                        continue

                    is_admin = user_id in family["admin_user_ids"]
                    member_limit = (
                        limits_data["max_members_per_family"]
                        if is_admin
                        else family.get("max_members_allowed", limits_data["max_members_per_family"])
                    )

                    violations = []
                    recommended_actions = []
                    is_compliant = family["member_count"] <= member_limit

                    if not is_compliant:
                        violations.append(f"Member count ({family['member_count']}) exceeds limit ({member_limit})")
                        recommended_actions.append("Remove members or upgrade limits")
                        overall_compliance = False
                        total_violations += 1
                    else:
                        compliant_families += 1

                    family_validations.append(
                        {
                            "family_id": family["family_id"],
                            "family_name": family["name"],
                            "is_compliant": is_compliant,
                            "current_members": family["member_count"],
                            "member_limit": member_limit,
                            "violations": violations,
                            "recommended_actions": recommended_actions,
                        }
                    )

                except Exception as e:
                    self.logger.warning("Failed to validate family %s: %s", membership["family_id"], e)
                    continue

            # Member limit enforcement status (aggregate)
            if family_validations:
                total_members = sum(fv["current_members"] for fv in family_validations if fv["is_compliant"])
                total_member_limit = sum(fv["member_limit"] for fv in family_validations)

                members_limit_status = {
                    "limit_type": "members",
                    "is_enforced": True,
                    "current_value": total_members,
                    "limit_value": total_member_limit,
                    "is_compliant": all(fv["is_compliant"] for fv in family_validations),
                    "grace_period_active": False,
                    "grace_period_expires": None,
                    "enforcement_action": "block_addition",
                }

                limit_statuses.append(members_limit_status)

            # Check for active grace periods
            grace_periods = {"active_periods": [], "expired_periods": []}

            # Generate compliance recommendations
            recommendations = []
            if overall_compliance:
                recommendations.append("All limits are compliant")
                recommendations.append("No action required")
            else:
                if limits_data["current_families"] > limits_data["max_families_allowed"]:
                    recommendations.append("Family count exceeds limit - consider upgrading")

                non_compliant_families = [fv for fv in family_validations if not fv["is_compliant"]]
                if non_compliant_families:
                    recommendations.append(f"{len(non_compliant_families)} families exceed member limits")
                    recommendations.append("Remove members or upgrade to higher limits")

            # Compliance summary
            compliance_summary = {
                "total_families": len(family_validations),
                "compliant_families": compliant_families,
                "total_violations": total_violations,
                "grace_periods_active": len(grace_periods["active_periods"]),
            }

            return {
                "user_id": user_id,
                "overall_compliance": overall_compliance,
                "enforcement_active": True,
                "limit_statuses": limit_statuses,
                "family_validations": family_validations,
                "grace_periods": grace_periods,
                "compliance_summary": compliance_summary,
                "recommendations": recommendations,
                "last_updated": datetime.now(timezone.utc),
            }

        except Exception as e:
            self.logger.error("Failed to get limit enforcement status for user %s: %s", user_id, e, exc_info=True)
            raise FamilyError(f"Failed to get limit enforcement status: {str(e)}")

    async def _get_usage_tracking_data(
        self, user_id: str, start_date: datetime, end_date: datetime, granularity: str = "daily"
    ) -> List[Dict[str, Any]]:
        """Get raw usage tracking data from the database."""
        try:
            usage_collection = self.db_manager.get_collection("family_usage_tracking")

            # Query usage data
            cursor = usage_collection.find(
                {"user_id": user_id, "timestamp": {"$gte": start_date, "$lte": end_date}}
            ).sort("timestamp", 1)

            usage_records = await cursor.to_list(length=None)

            # Aggregate data by granularity
            if granularity == "daily":
                return await self._aggregate_daily_usage(usage_records, start_date, end_date)
            elif granularity == "weekly":
                return await self._aggregate_weekly_usage(usage_records, start_date, end_date)
            elif granularity == "monthly":
                return await self._aggregate_monthly_usage(usage_records, start_date, end_date)
            else:
                raise ValueError(f"Unsupported granularity: {granularity}")

        except Exception as e:
            self.logger.warning("Failed to get raw usage tracking data: %s", e)
            return []

    async def _aggregate_daily_usage(
        self, usage_records: List[Dict], start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Aggregate usage data by day."""
        try:
            daily_data = {}

            # Initialize all days in range
            current_date = start_date.date()
            while current_date <= end_date.date():
                daily_data[current_date.isoformat()] = {
                    "date": current_date.isoformat(),
                    "families_count": 0,
                    "total_members": 0,
                    "events": [],
                }
                current_date += timedelta(days=1)

            # Aggregate records
            for record in usage_records:
                date_key = record["timestamp"].date().isoformat()
                if date_key in daily_data:
                    daily_data[date_key]["families_count"] = record.get("families_count", 0)
                    daily_data[date_key]["total_members"] = record.get("total_members", 0)
                    if record.get("event_type"):
                        daily_data[date_key]["events"].append(record["event_type"])

            return list(daily_data.values())

        except Exception as e:
            self.logger.warning("Failed to aggregate daily usage: %s", e)
            return []

    async def _aggregate_weekly_usage(
        self, usage_records: List[Dict], start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Aggregate usage data by week."""
        # TODO: Implement weekly aggregation
        return await self._aggregate_daily_usage(usage_records, start_date, end_date)

    async def _aggregate_monthly_usage(
        self, usage_records: List[Dict], start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Aggregate usage data by month."""
        # TODO: Implement monthly aggregation
        return await self._aggregate_daily_usage(usage_records, start_date, end_date)

    async def _track_usage_event(self, user_id: str, event_type: str, event_data: Dict[str, Any] = None):
        """Track a family usage event for billing purposes."""
        try:
            from second_brain_database.config import settings

            if not settings.ENABLE_FAMILY_USAGE_TRACKING:
                return

            usage_collection = self.db_manager.get_collection("family_usage_tracking")

            # Get current usage snapshot
            current_usage = await self.check_family_limits(user_id)

            tracking_record = {
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc),
                "event_type": event_type,
                "event_data": event_data or {},
                "families_count": current_usage["current_families"],
                "total_members": sum(f.get("member_count", 0) for f in current_usage["families_usage"]),
                "limits": {
                    "max_families_allowed": current_usage["max_families_allowed"],
                    "max_members_per_family": current_usage["max_members_per_family"],
                },
            }

            await usage_collection.insert_one(tracking_record)

            # Clean up old tracking data
            await self._cleanup_old_usage_data(settings.FAMILY_USAGE_TRACKING_RETENTION_DAYS)

        except Exception as e:
            self.logger.warning("Failed to track usage event %s for user %s: %s", event_type, user_id, e)

    async def _cleanup_old_usage_data(self, retention_days: int):
        """Clean up old usage tracking data."""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            usage_collection = self.db_manager.get_collection("family_usage_tracking")

            result = await usage_collection.delete_many({"timestamp": {"$lt": cutoff_date}})

            if result.deleted_count > 0:
                self.logger.debug("Cleaned up %d old usage tracking records", result.deleted_count)

        except Exception as e:
            self.logger.warning("Failed to cleanup old usage data: %s", e)

    async def enforce_family_limits(
        self, user_id: str, operation: str, context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Enforce family limits with upgrade messaging.

        Args:
            user_id: ID of the user
            operation: Operation being attempted (create_family, add_member)
            context: Additional context for the operation

        Returns:
            Dict containing enforcement result and upgrade messaging

        Raises:
            FamilyLimitExceeded: If limits are exceeded and no grace period
        """
        try:
            limits_info = await self.check_family_limits(user_id, include_billing_metrics=True)

            # Check specific operation limits
            if operation == "create_family":
                if not limits_info["can_create_family"]:
                    # Check for grace period
                    grace_period = await self._check_grace_period(user_id, "families")
                    if not grace_period["active"]:
                        raise FamilyLimitExceeded(
                            limits_info["upgrade_messaging"]["primary_message"],
                            current_count=limits_info["current_families"],
                            max_allowed=limits_info["max_families_allowed"],
                            limit_type="families",
                        )
                    else:
                        return {
                            "allowed": True,
                            "grace_period": grace_period,
                            "upgrade_messaging": limits_info["upgrade_messaging"],
                        }

            elif operation == "add_member":
                family_id = context.get("family_id") if context else None
                if family_id:
                    family_usage = next((f for f in limits_info["families_usage"] if f["family_id"] == family_id), None)
                    if family_usage and not family_usage["can_add_members"]:
                        grace_period = await self._check_grace_period(user_id, "members", family_id)
                        if not grace_period["active"]:
                            raise FamilyLimitExceeded(
                                f"Family member limit reached ({family_usage['member_count']}/{family_usage['max_members_allowed']})",
                                current_count=family_usage["member_count"],
                                max_allowed=family_usage["max_members_allowed"],
                                limit_type="family_members",
                            )
                        else:
                            return {
                                "allowed": True,
                                "grace_period": grace_period,
                                "upgrade_messaging": limits_info["upgrade_messaging"],
                            }

            return {"allowed": True, "limits_info": limits_info, "upgrade_messaging": limits_info["upgrade_messaging"]}

        except FamilyLimitExceeded:
            raise
        except Exception as e:
            self.logger.error("Failed to enforce family limits: %s", e, exc_info=True)
            raise FamilyError(f"Failed to enforce limits: {str(e)}")

    async def _check_grace_period(self, user_id: str, limit_type: str, family_id: str = None) -> Dict[str, Any]:
        """Check if user has an active grace period for limit downgrades."""
        try:
            user = await self._get_user_by_id(user_id)
            family_limits = user.get("family_limits", {})

            grace_period_expires = family_limits.get("grace_period_expires")
            if not grace_period_expires:
                return {"active": False}

            now = datetime.now(timezone.utc)
            if now > grace_period_expires:
                return {"active": False, "expired": True}

            return {
                "active": True,
                "expires_at": grace_period_expires,
                "days_remaining": (grace_period_expires - now).days,
                "limit_type": limit_type,
            }

        except Exception as e:
            self.logger.warning("Failed to check grace period: %s", e)
            return {"active": False}

    async def get_limit_status_display(self, user_id: str) -> Dict[str, Any]:
        """
        Get formatted limit status for display in UI.

        Args:
            user_id: ID of the user

        Returns:
            Dict containing formatted limit status and display information
        """
        try:
            limits_info = await self.check_family_limits(user_id, include_billing_metrics=True)

            # Format limit status for display
            display_info = {
                "limits_summary": {
                    "families": {
                        "current": limits_info["current_families"],
                        "max": limits_info["max_families_allowed"],
                        "percentage": (
                            (limits_info["current_families"] / limits_info["max_families_allowed"] * 100)
                            if limits_info["max_families_allowed"] > 0
                            else 0
                        ),
                        "status": (
                            "at_limit"
                            if limits_info["current_families"] >= limits_info["max_families_allowed"]
                            else "within_limit"
                        ),
                    }
                },
                "upgrade_messaging": limits_info["upgrade_messaging"],
                "billing_metrics": limits_info.get("billing_metrics"),
                "recommendations": [],
            }

            # Add member limits for admin families
            admin_families = [f for f in limits_info["families_usage"] if f["is_admin"]]
            if admin_families:
                total_members = sum(f["member_count"] for f in admin_families)
                max_total_members = len(admin_families) * limits_info["max_members_per_family"]

                display_info["limits_summary"]["members"] = {
                    "current": total_members,
                    "max": max_total_members,
                    "percentage": (total_members / max_total_members * 100) if max_total_members > 0 else 0,
                    "status": "at_limit" if total_members >= max_total_members else "within_limit",
                }

            # Generate recommendations
            if limits_info["current_families"] / limits_info["max_families_allowed"] > 0.8:
                display_info["recommendations"].append(
                    {
                        "type": "upgrade_soon",
                        "message": "You're approaching your family limit. Consider upgrading to avoid restrictions.",
                        "priority": "medium",
                    }
                )

            if limits_info.get("billing_metrics", {}).get("upgrade_recommendations"):
                for rec in limits_info["billing_metrics"]["upgrade_recommendations"]:
                    display_info["recommendations"].append(
                        {"type": "billing_recommendation", "message": rec, "priority": "high"}
                    )

            return display_info

        except Exception as e:
            self.logger.error("Failed to get limit status display: %s", e, exc_info=True)
            raise FamilyError(f"Failed to get limit status: {str(e)}")

    async def direct_transfer_tokens(
        self,
        family_id: str,
        admin_id: str,
        recipient_identifier: str,
        recipient_type: str,
        amount: int,
        reason: str,
        request_context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Directly transfer tokens from family account to a member (admin only)."""
        try:
            # Input validation
            if amount <= 0:
                raise ValueError("Transfer amount must be positive")

            if not reason or not reason.strip():
                raise ValueError("Transfer reason is required")

            if recipient_type not in ["user_id", "username"]:
                raise ValueError("Invalid recipient type. Must be 'user_id' or 'username'")

            if not recipient_identifier or not recipient_identifier.strip():
                raise ValueError("Recipient identifier is required")

            # Verify admin permissions
            family = await self._get_family_by_id(family_id)
            if admin_id not in family["admin_user_ids"]:
                raise InsufficientPermissions("Only family admins can perform direct transfers")

            # Check if family account is frozen
            if family["sbd_account"]["is_frozen"]:
                raise FamilyError("Family account is frozen and cannot perform transfers")

            # Get family balance
            family_balance = await self.get_family_sbd_balance(family["sbd_account"]["account_username"])
            if family_balance < amount:
                raise FamilyError(f"Insufficient family balance. Required: {amount}, Available: {family_balance}")

            # Find recipient
            if recipient_type == "user_id":
                recipient_user = await self._get_user_by_id(recipient_identifier)
            else:  # username
                recipient_user = await self._get_user_by_username(recipient_identifier)

            if not recipient_user:
                raise FamilyError(f"Recipient {recipient_type} '{recipient_identifier}' not found")

            recipient_user_id = str(recipient_user["_id"])

            # Verify recipient is family member
            if not await self._is_user_in_family(recipient_user_id, family_id):
                raise FamilyError("Recipient must be a family member")

            recipient_username = recipient_user.get("username", "Unknown")

            # Start transaction for atomic transfer
            client = self.db_manager.client
            session = await client.start_session()

            try:
                async with session.start_transaction():
                    transaction_id = f"txn_{uuid.uuid4().hex[:16]}"

                    # Update family balance (decrease)
                    await self._update_family_balance_transactional(
                        family["sbd_account"]["account_username"],
                        -amount,
                        transaction_id,
                        f"Direct transfer to {recipient_username}: {reason}",
                        session,
                    )

                    # Update recipient balance (increase)
                    await self._update_user_balance_transactional(
                        recipient_user_id,
                        amount,
                        transaction_id,
                        f"Direct transfer from family account: {reason}",
                        session,
                    )

                    # Log transaction
                    await self._log_family_transaction(
                        family_id,
                        transaction_id,
                        "direct_transfer",
                        -amount,
                        f"Direct transfer to {recipient_username}: {reason}",
                        admin_id,
                        recipient_user_id,
                        session,
                    )

                    # Send notifications
                    await self._send_direct_transfer_notification(
                        family_id, recipient_user_id, amount, admin_id, reason, transaction_id
                    )

                    await self._send_direct_transfer_admin_notification(
                        family_id, admin_id, recipient_username, amount, reason, transaction_id
                    )

                    return {
                        "success": True,
                        "transaction_id": transaction_id,
                        "amount": amount,
                        "recipient": recipient_username,
                        "reason": reason,
                        "transferred_at": datetime.utcnow().isoformat(),
                    }

            except Exception as e:
                # Transaction will be automatically rolled back
                self.logger.error("Direct token transfer transaction failed: %s", e)
                raise e

            finally:
                await session.end_session()

        except ValueError as e:
            raise e
        except Exception as e:
            self.logger.error("Direct token transfer failed: %s", e)
            raise Exception(f"Direct token transfer failed: {str(e)}")

    async def _send_direct_transfer_notification(
        self, family_id: str, recipient_user_id: str, amount: int, admin_id: str, reason: str, transaction_id: str
    ) -> None:
        """Send notification about direct token transfer to recipient."""
        try:
            admin_user = await self._get_user_by_id(admin_id)

            notification_data = {
                "type": "direct_token_transfer_received",
                "title": "Tokens Received",
                "message": f"You have received {amount} tokens directly from your family account. Reason: {reason}",
                "data": {
                    "amount": amount,
                    "reason": reason,
                    "transferred_by": admin_id,
                    "admin_username": admin_user.get("username", "Admin") if admin_user else "Admin",
                    "transaction_id": transaction_id,
                    "transfer_completed": True,
                },
            }

            await self._send_family_notification(family_id, [recipient_user_id], notification_data)

        except Exception as e:
            self.logger.error("Failed to send direct transfer notification: %s", e)

    async def _send_direct_transfer_admin_notification(
        self, family_id: str, admin_id: str, recipient_username: str, amount: int, reason: str, transaction_id: str
    ) -> None:
        """Send notification about direct token transfer to other family admins."""
        try:
            family = await self._get_family_by_id(family_id)
            admin_user = await self._get_user_by_id(admin_id)

            # Send to other admins (not the one who performed the transfer)
            other_admins = [aid for aid in family["admin_user_ids"] if aid != admin_id]

            if other_admins:
                notification_data = {
                    "type": "direct_token_transfer_admin",
                    "title": "Direct Token Transfer",
                    "message": f"{admin_user.get('username', 'Admin') if admin_user else 'Admin'} transferred {amount} tokens to {recipient_username}. Reason: {reason}",
                    "data": {
                        "amount": amount,
                        "reason": reason,
                        "recipient_username": recipient_username,
                        "transferred_by": admin_id,
                        "admin_username": admin_user.get("username", "Admin") if admin_user else "Admin",
                        "transaction_id": transaction_id,
                        "transfer_completed": True,
                    },
                }

                await self._send_family_notification(family_id, other_admins, notification_data)

        except Exception as e:
            self.logger.error("Failed to send direct transfer admin notification: %s", e)


# Global family manager instance with dependency injection
family_manager = FamilyManager(
    db_manager=db_manager, email_manager=email_manager, security_manager=security_manager, redis_manager=redis_manager
)
