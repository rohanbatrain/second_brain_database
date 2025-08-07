"""
Family Manager for handling family relationships, SBD token accounts, and member management.

This module provides the FamilyManager class, which manages family creation,
member invitations, bidirectional relationships, and SBD token integration
following the established manager patterns in the codebase with enterprise-grade
patterns including dependency injection, transaction safety, and comprehensive
error handling.

Enterprise Features:
    - Dependency injection for testability and modularity
    - Transaction safety with MongoDB sessions for critical operations
    - Comprehensive error handling with custom exception hierarchy
    - Secure token generation using cryptographically secure methods
    - Configurable family limits with real-time validation
    - Comprehensive audit logging for all operations
    - Rate limiting integration for abuse prevention

Logging:
    - Uses the centralized logging manager with structured context
    - Logs all family operations, SBD transactions, and security events
    - Performance metrics tracking for all database operations
    - All exceptions are logged with full traceback and context
"""

import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Protocol, runtime_checkable

from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.client_session import ClientSession

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.security_manager import security_manager

logger = get_logger(prefix="[FamilyManager]")

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
    "cousin": "cousin"
}

# Dependency injection protocols for enterprise patterns
@runtime_checkable
class DatabaseManagerProtocol(Protocol):
    """Protocol for database manager dependency injection."""
    async def get_collection(self, collection_name: str) -> Any: ...
    def log_query_start(self, collection: str, operation: str, context: Dict[str, Any]) -> float: ...
    def log_query_success(self, collection: str, operation: str, start_time: float, count: int, info: str = None) -> None: ...
    def log_query_error(self, collection: str, operation: str, start_time: float, error: Exception, context: Dict[str, Any]) -> None: ...

@runtime_checkable
class EmailManagerProtocol(Protocol):
    """Protocol for email manager dependency injection."""
    async def send_family_invitation_email(self, to_email: str, inviter_username: str, family_name: str, 
                                         relationship_type: str, accept_link: str, decline_link: str, expires_at: str) -> bool: ...

@runtime_checkable
class SecurityManagerProtocol(Protocol):
    """Protocol for security manager dependency injection."""
    async def check_rate_limit(self, request: Any, action: str, rate_limit_requests: int = None, rate_limit_period: int = None) -> None: ...

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
        super().__init__(message, "FAMILY_LIMIT_EXCEEDED", {
            "current_count": current_count,
            "max_allowed": max_allowed,
            "limit_type": limit_type,
            "upgrade_required": True
        })


class InvalidRelationship(FamilyError):
    """Relationship validation failed with detailed context."""
    
    def __init__(self, message: str, relationship_type: str = None, valid_types: List[str] = None):
        super().__init__(message, "INVALID_RELATIONSHIP", {
            "relationship_type": relationship_type,
            "valid_types": valid_types or list(RELATIONSHIP_TYPES.keys())
        })


class FamilyNotFound(FamilyError):
    """Family does not exist or is not accessible."""
    
    def __init__(self, message: str, family_id: str = None):
        super().__init__(message, "FAMILY_NOT_FOUND", {"family_id": family_id})


class InvitationNotFound(FamilyError):
    """Invitation does not exist, expired, or already processed."""
    
    def __init__(self, message: str, invitation_id: str = None, status: str = None):
        super().__init__(message, "INVITATION_NOT_FOUND", {
            "invitation_id": invitation_id,
            "status": status
        })


class InsufficientPermissions(FamilyError):
    """User lacks required permissions for the operation."""
    
    def __init__(self, message: str, required_role: str = None, user_role: str = None):
        super().__init__(message, "INSUFFICIENT_PERMISSIONS", {
            "required_role": required_role,
            "user_role": user_role
        })


class AccountFrozen(FamilyError):
    """Family SBD account is frozen and cannot be used."""
    
    def __init__(self, message: str, family_id: str = None, frozen_by: str = None, frozen_at: datetime = None):
        super().__init__(message, "ACCOUNT_FROZEN", {
            "family_id": family_id,
            "frozen_by": frozen_by,
            "frozen_at": frozen_at.isoformat() if frozen_at else None
        })


class SpendingLimitExceeded(FamilyError):
    """Transaction exceeds user's spending limit."""
    
    def __init__(self, message: str, amount: int = None, limit: int = None, user_id: str = None):
        super().__init__(message, "SPENDING_LIMIT_EXCEEDED", {
            "amount": amount,
            "limit": limit,
            "user_id": user_id
        })


class TokenRequestNotFound(FamilyError):
    """Token request does not exist or is not accessible."""
    
    def __init__(self, message: str, request_id: str = None, status: str = None):
        super().__init__(message, "TOKEN_REQUEST_NOT_FOUND", {
            "request_id": request_id,
            "status": status
        })


class TransactionError(FamilyError):
    """Database transaction failed with rollback information."""
    
    def __init__(self, message: str, operation: str = None, rollback_successful: bool = None):
        super().__init__(message, "TRANSACTION_ERROR", {
            "operation": operation,
            "rollback_successful": rollback_successful
        })


class ValidationError(FamilyError):
    """Input validation failed with field-specific details."""
    
    def __init__(self, message: str, field: str = None, value: Any = None, constraint: str = None):
        super().__init__(message, "VALIDATION_ERROR", {
            "field": field,
            "value": str(value) if value is not None else None,
            "constraint": constraint
        })


class RateLimitExceeded(FamilyError):
    """Rate limit exceeded for family operations."""
    
    def __init__(self, message: str, action: str = None, limit: int = None, window: int = None):
        super().__init__(message, "RATE_LIMIT_EXCEEDED", {
            "action": action,
            "limit": limit,
            "window_seconds": window
        })


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
        redis_manager: RedisManagerProtocol = None
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
        self.db_manager = db_manager or globals()['db_manager']
        self.email_manager = email_manager or globals()['email_manager']
        self.security_manager = security_manager or globals()['security_manager']
        self.redis_manager = redis_manager or globals()['redis_manager']
        
        self.logger = logger
        self.logger.debug("FamilyManager initialized with dependency injection")
        
        # Cache for frequently accessed data
        self._user_cache = {}
        self._family_cache = {}
        self._cache_ttl = 300  # 5 minutes cache TTL

    async def create_family(self, user_id: str, name: Optional[str] = None, request_context: Dict[str, Any] = None) -> Dict[str, Any]:
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
        operation_context = {
            "user_id": user_id, 
            "name": name, 
            "operation": "create_family",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        start_time = self.db_manager.log_query_start("families", "create_family", operation_context)
        
        # Rate limiting check
        if request_context:
            try:
                await self._check_rate_limit(request_context, "family_creation", FAMILY_CREATION_RATE_LIMIT, 3600)
            except Exception as e:
                raise RateLimitExceeded(
                    "Family creation rate limit exceeded", 
                    action="family_creation", 
                    limit=FAMILY_CREATION_RATE_LIMIT, 
                    window=3600
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
            
            # Start transaction
            session = await client.start_session()
            
            async with session.start_transaction():
                now = datetime.now(timezone.utc)
                
                # Create comprehensive family document
                family_doc = await self._build_family_document(
                    family_id, name, user_id, sbd_account_username, now
                )
                
                # Insert family document within transaction
                families_collection = self.db_manager.get_collection("families")
                await families_collection.insert_one(family_doc, session=session)
                
                # Create virtual SBD account within transaction
                await self._create_virtual_sbd_account_transactional(
                    sbd_account_username, family_id, session
                )
                
                # Update user's family membership within transaction
                await self._add_user_to_family_membership_transactional(
                    user_id, family_id, "admin", now, session
                )
                
                # Cache the new family for performance
                self._cache_family(family_id, family_doc)
                
                # Log successful creation
                self.db_manager.log_query_success(
                    "families", "create_family", start_time, 1, 
                    f"Family created with transaction: {family_id}"
                )
                
                self.logger.info(
                    "Family created successfully with transaction safety: %s by user %s", 
                    family_id, user_id,
                    extra={
                        "family_id": family_id,
                        "user_id": user_id,
                        "sbd_account": sbd_account_username,
                        "transaction_id": str(session.session_id) if session else None
                    }
                )
                
                return {
                    "family_id": family_id,
                    "name": name,
                    "admin_user_ids": [user_id],
                    "member_count": 1,
                    "created_at": now,
                    "sbd_account": {
                        "account_username": sbd_account_username,
                        "balance": 0,
                        "is_frozen": False
                    },
                    "limits_info": limits_info,
                    "transaction_safe": True
                }
                
        except (FamilyLimitExceeded, ValidationError, RateLimitExceeded) as e:
            # These are expected validation errors, don't wrap them
            self.db_manager.log_query_error("families", "create_family", start_time, e, operation_context)
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
            self.logger.error(
                "Failed to create family for user %s: %s", user_id, e, 
                exc_info=True,
                extra={
                    "user_id": user_id,
                    "family_name": name,
                    "rollback_successful": rollback_successful,
                    "transaction_id": str(session.session_id) if session else None
                }
            )
            
            raise TransactionError(
                f"Failed to create family: {str(e)}", 
                operation="create_family",
                rollback_successful=rollback_successful
            )
            
        finally:
            if session:
                await session.end_session()

    async def invite_member(self, family_id: str, inviter_id: str, identifier: str, relationship_type: str, 
                           identifier_type: str = "email", request_context: Dict[str, Any] = None) -> Dict[str, Any]:
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
            "timestamp": datetime.now(timezone.utc).isoformat()
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
                    window=3600
                )
        
        session = None
        
        try:
            # Comprehensive input validation
            await self._validate_invitation_input(family_id, inviter_id, identifier, relationship_type, identifier_type)
            
            # Verify family exists and user has admin permissions
            family = await self._get_family_by_id(family_id)
            if inviter_id not in family["admin_user_ids"]:
                raise InsufficientPermissions(
                    "Only family admins can invite members", 
                    required_role="admin", 
                    user_role="member"
                )
            
            # Check family member limits with detailed context
            await self._check_family_member_limits_detailed(family_id, inviter_id)
            
            # Find and validate invitee user
            invitee_user = await self._find_and_validate_invitee(identifier, identifier_type)
            invitee_id = str(invitee_user["_id"])
            
            # Check for existing membership or pending invitations
            await self._check_existing_membership_and_invitations(invitee_id, family_id)
            
            # Validate relationship logic (prevent contradictory relationships)
            await self._validate_relationship_logic(inviter_id, invitee_id, relationship_type, family_id)
            
            # Start transaction for invitation creation
            client = self.db_manager.client
            session = await client.start_session()
            
            async with session.start_transaction():
                # Generate secure invitation with cryptographic token
                invitation_data = await self._generate_secure_invitation(
                    family_id, inviter_id, invitee_user, relationship_type
                )
                
                # Insert invitation within transaction
                invitations_collection = self.db_manager.get_collection("family_invitations")
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
                            "email_attempts": 1
                        }
                    },
                    session=session
                )
                
                # Log successful invitation
                self.db_manager.log_query_success(
                    "family_invitations", "invite_member", start_time, 1,
                    f"Invitation sent with transaction: {invitation_data['invitation_id']}"
                )
                
                self.logger.info(
                    "Family invitation sent successfully: %s to %s (%s) for family %s", 
                    invitation_data["invitation_id"], identifier, identifier_type, family_id,
                    extra={
                        "invitation_id": invitation_data["invitation_id"],
                        "family_id": family_id,
                        "inviter_id": inviter_id,
                        "invitee_id": invitee_id,
                        "relationship_type": relationship_type,
                        "email_sent": email_sent,
                        "transaction_id": str(session.session_id) if session else None
                    }
                )
                
                return {
                    "invitation_id": invitation_data["invitation_id"],
                    "family_name": family["name"],
                    "invitee_email": invitee_user.get("email", ""),
                    "invitee_username": invitee_user.get("username", ""),
                    "relationship_type": relationship_type,
                    "expires_at": invitation_data["expires_at"],
                    "status": "pending",
                    "email_sent": email_sent,
                    "transaction_safe": True
                }
                
        except (FamilyNotFound, InsufficientPermissions, InvalidRelationship, ValidationError, 
                RateLimitExceeded, FamilyLimitExceeded) as e:
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
                "Failed to invite member to family %s: %s", family_id, e, 
                exc_info=True,
                extra={
                    "family_id": family_id,
                    "inviter_id": inviter_id,
                    "identifier": identifier,
                    "rollback_successful": rollback_successful,
                    "transaction_id": str(session.session_id) if session else None
                }
            )
            
            raise TransactionError(
                f"Failed to send invitation: {str(e)}", 
                operation="invite_member",
                rollback_successful=rollback_successful
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
        start_time = db_manager.log_query_start("family_invitations", "respond_to_invitation",
                                              {"invitation_id": invitation_id, "action": action})
        
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
            
            if datetime.now(timezone.utc) > invitation["expires_at"]:
                raise InvitationNotFound("Invitation has expired")
            
            now = datetime.now(timezone.utc)
            
            if action.lower() == "accept":
                # Accept invitation - create bidirectional relationship
                await self._create_bidirectional_relationship(
                    invitation["family_id"],
                    invitation["inviter_user_id"],
                    user_id,
                    invitation["relationship_type"]
                )
                
                # Add user to family membership
                await self._add_user_to_family_membership(user_id, invitation["family_id"], "member", now)
                
                # Update family member count
                await self._increment_family_member_count(invitation["family_id"])
                
                # Update invitation status
                await invitations_collection.update_one(
                    {"invitation_id": invitation_id},
                    {
                        "$set": {
                            "status": "accepted",
                            "responded_at": now
                        }
                    }
                )
                
                self.logger.info("Family invitation accepted: %s by user %s", invitation_id, user_id)
                
                return {
                    "status": "accepted",
                    "family_id": invitation["family_id"],
                    "relationship_type": invitation["relationship_type"],
                    "message": "Successfully joined the family"
                }
                
            else:  # decline
                # Update invitation status
                await invitations_collection.update_one(
                    {"invitation_id": invitation_id},
                    {
                        "$set": {
                            "status": "declined",
                            "responded_at": now
                        }
                    }
                )
                
                self.logger.info("Family invitation declined: %s by user %s", invitation_id, user_id)
                
                return {
                    "status": "declined",
                    "message": "Invitation declined"
                }
            
            db_manager.log_query_success("family_invitations", "respond_to_invitation", start_time, 1,
                                       f"Invitation {action}ed: {invitation_id}")
            
        except (InvitationNotFound, InsufficientPermissions):
            db_manager.log_query_error("family_invitations", "respond_to_invitation", start_time,
                                     Exception("Validation error"), {"invitation_id": invitation_id})
            raise
        except Exception as e:
            db_manager.log_query_error("family_invitations", "respond_to_invitation", start_time, e,
                                     {"invitation_id": invitation_id})
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
        start_time = db_manager.log_query_start("family_invitations", "respond_to_invitation_by_token",
                                              {"token": invitation_token[:8] + "...", "action": action})
        
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
            return await self.respond_to_invitation(
                invitation["invitation_id"], 
                invitation["invitee_user_id"], 
                action
            )
            
        except (InvitationNotFound, FamilyError):
            db_manager.log_query_error("family_invitations", "respond_to_invitation_by_token", start_time,
                                     Exception("Validation error"), {"token": invitation_token[:8] + "..."})
            raise
        except Exception as e:
            db_manager.log_query_error("family_invitations", "respond_to_invitation_by_token", start_time, e,
                                     {"token": invitation_token[:8] + "..."})
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
            
            families_cursor = families_collection.find({
                "family_id": {"$in": family_ids},
                "is_active": True
            })
            
            families = []
            async for family in families_cursor:
                # Find user's role in this family
                user_membership = next(
                    (m for m in family_memberships if m["family_id"] == family["family_id"]), 
                    None
                )
                
                if user_membership:
                    # Get SBD account balance
                    sbd_balance = await self._get_sbd_account_balance(family["sbd_account"]["account_username"])
                    
                    families.append({
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
                            "can_spend": user_membership.get("spending_permissions", {}).get("can_spend", False)
                        }
                    })
            
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
        start_time = db_manager.log_query_start("family_relationships", "get_family_members", 
                                              {"family_id": family_id, "user_id": user_id})
        
        try:
            # Verify family exists and user is a member
            family = await self._get_family_by_id(family_id)
            if not await self._is_user_in_family(user_id, family_id):
                raise InsufficientPermissions("You must be a family member to view family members")
            
            # Get all relationships for this family
            relationships_collection = db_manager.get_collection("family_relationships")
            relationships_cursor = relationships_collection.find({
                "family_id": family_id,
                "status": "active"
            })
            
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
                                "relationships": []
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
                    members[user_a_id]["relationships"].append({
                        "related_user_id": user_b_id,
                        "related_username": members[user_b_id]["username"],
                        "relationship_type": relationship["relationship_type_a_to_b"],
                        "relationship_id": relationship["relationship_id"],
                        "created_at": relationship["created_at"]
                    })
                    
                    # Add relationship from B's perspective to A
                    members[user_b_id]["relationships"].append({
                        "related_user_id": user_a_id,
                        "related_username": members[user_a_id]["username"],
                        "relationship_type": relationship["relationship_type_b_to_a"],
                        "relationship_id": relationship["relationship_id"],
                        "created_at": relationship["created_at"]
                    })
            
            # Convert to list and add family membership info
            members_list = []
            for member_id, member_info in members.items():
                # Get user's family membership details
                member_user = await self._get_user_by_id(member_id)
                family_memberships = member_user.get("family_memberships", [])
                family_membership = next(
                    (m for m in family_memberships if m["family_id"] == family_id), 
                    None
                )
                
                if family_membership:
                    member_info["joined_at"] = family_membership["joined_at"]
                    member_info["spending_permissions"] = family_membership.get("spending_permissions", {})
                
                members_list.append(member_info)
            
            # Sort by join date
            members_list.sort(key=lambda x: x.get("joined_at", datetime.min.replace(tzinfo=timezone.utc)))
            
            db_manager.log_query_success("family_relationships", "get_family_members", start_time, 
                                       len(members_list), f"Retrieved {len(members_list)} family members")
            
            self.logger.info("Retrieved %d family members for family %s", len(members_list), family_id)
            
            return members_list
            
        except (FamilyNotFound, InsufficientPermissions):
            db_manager.log_query_error("family_relationships", "get_family_members", start_time,
                                     Exception("Validation error"), {"family_id": family_id})
            raise
        except Exception as e:
            db_manager.log_query_error("family_relationships", "get_family_members", start_time, e,
                                     {"family_id": family_id})
            self.logger.error("Failed to get family members for family %s: %s", family_id, e, exc_info=True)
            raise FamilyError(f"Failed to retrieve family members: {str(e)}")

    async def check_family_limits(self, user_id: str) -> Dict[str, Any]:
        """
        Check user's family limits and current usage.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Dict containing limits and usage information
        """
        try:
            user = await self._get_user_by_id(user_id)
            
            # Get family limits (with defaults)
            family_limits = user.get("family_limits", {})
            max_families = family_limits.get("max_families_allowed", DEFAULT_MAX_FAMILIES)
            max_members_per_family = family_limits.get("max_members_per_family", DEFAULT_MAX_MEMBERS_PER_FAMILY)
            
            # Get current usage
            family_memberships = user.get("family_memberships", [])
            current_families = len(family_memberships)
            
            # Get detailed family usage
            families_usage = []
            for membership in family_memberships:
                family = await self._get_family_by_id(membership["family_id"])
                if family:
                    families_usage.append({
                        "family_id": family["family_id"],
                        "name": family["name"],
                        "member_count": family["member_count"],
                        "is_admin": user_id in family["admin_user_ids"]
                    })
            
            return {
                "max_families_allowed": max_families,
                "max_members_per_family": max_members_per_family,
                "current_families": current_families,
                "families_usage": families_usage,
                "can_create_family": current_families < max_families,
                "upgrade_required": current_families >= max_families
            }
            
        except Exception as e:
            self.logger.error("Failed to check family limits for user %s: %s", user_id, e, exc_info=True)
            raise FamilyError(f"Failed to check family limits: {str(e)}")

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
                    field="name", value=name, constraint="min_length_2"
                )
            if len(name) > 100:
                raise ValidationError(
                    "Family name must be less than 100 characters", 
                    field="name", value=name, constraint="max_length_100"
                )
            # Check for reserved prefixes
            for prefix in RESERVED_PREFIXES:
                if name.lower().startswith(prefix):
                    raise ValidationError(
                        f"Family name cannot start with reserved prefix '{prefix}'",
                        field="name", value=name, constraint="no_reserved_prefix"
                    )
    
    async def _check_family_creation_limits(self, user_id: str) -> Dict[str, Any]:
        """Check if user can create a new family and return detailed limits info."""
        limits = await self.check_family_limits(user_id)
        if not limits["can_create_family"]:
            raise FamilyLimitExceeded(
                f"Maximum families limit reached ({limits['current_families']}/{limits['max_families_allowed']})",
                current_count=limits['current_families'],
                max_allowed=limits['max_families_allowed'],
                limit_type="families"
            )
        return limits
    
    async def _generate_unique_sbd_username(self, family_name: str) -> str:
        """Generate and ensure unique SBD account username with collision handling."""
        return await self.generate_collision_resistant_family_username(family_name)
    
    async def _build_family_document(self, family_id: str, name: str, user_id: str, 
                                   sbd_account_username: str, timestamp: datetime) -> Dict[str, Any]:
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
                        "updated_at": timestamp
                    }
                },
                "notification_settings": {
                    "notify_on_spend": True,
                    "notify_on_deposit": True,
                    "large_transaction_threshold": 1000,
                    "notify_admins_only": False
                }
            },
            "settings": {
                "allow_member_invites": False,
                "visibility": "private",
                "auto_approval_threshold": AUTO_APPROVAL_THRESHOLD,
                "request_expiry_hours": TOKEN_REQUEST_EXPIRY_HOURS
            },
            "succession_plan": {
                "backup_admins": [],
                "recovery_contacts": []
            },
            "audit_trail": {
                "created_by": user_id,
                "created_at": timestamp,
                "last_modified_by": user_id,
                "last_modified_at": timestamp,
                "version": 1
            }
        }
    
    async def _create_virtual_sbd_account_transactional(self, username: str, family_id: str, session: ClientSession) -> None:
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
                "rate_limit_enabled": True
            },
            
            # Audit trail initialization
            "audit_trail": {
                "created_by_system": "family_manager",
                "creation_timestamp": now,
                "creation_context": {
                    "family_id": family_id,
                    "account_type": "family_virtual",
                    "initial_balance": 0
                },
                "last_activity": now,
                "activity_count": 0,
                "security_events": []
            },
            
            # Access controls
            "access_controls": {
                "authorized_family_members": [],  # Will be populated when members join
                "spending_permissions": {},  # Will be managed by family admins
                "frozen": False,
                "frozen_by": None,
                "frozen_at": None,
                "freeze_reason": None
            },
            
            # Data retention settings
            "retention_policy": {
                "retain_transactions": True,
                "retention_period_days": VIRTUAL_ACCOUNT_RETENTION_DAYS,
                "auto_cleanup_enabled": True,
                "cleanup_scheduled": False
            },
            
            # Performance and monitoring
            "performance_metrics": {
                "total_transactions": 0,
                "total_volume_in": 0,
                "total_volume_out": 0,
                "last_transaction_at": None,
                "peak_balance": 0,
                "peak_balance_at": None
            }
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
                    "session_id": str(session.session_id) if session else None
                },
                session=session
            )
            
            self.logger.info(
                "Virtual SBD account created with comprehensive audit trail: %s for family %s (account_id: %s)", 
                username, family_id, account_id,
                extra={
                    "username": username,
                    "family_id": family_id,
                    "account_id": account_id,
                    "transaction_safe": True,
                    "audit_enabled": True
                }
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to create virtual SBD account: %s", e,
                exc_info=True,
                extra={
                    "username": username,
                    "family_id": family_id,
                    "account_id": account_id
                }
            )
            raise TransactionError(
                f"Failed to create virtual SBD account: {str(e)}",
                operation="create_virtual_account"
            )
    
    async def _add_user_to_family_membership_transactional(self, user_id: str, family_id: str, 
                                                         role: str, joined_at: datetime, session: ClientSession) -> None:
        """Add user to family membership list within a database transaction."""
        users_collection = self.db_manager.get_collection("users")
        
        membership = {
            "family_id": family_id,
            "role": role,
            "joined_at": joined_at,
            "spending_permissions": {
                "can_spend": role == "admin",
                "spending_limit": -1 if role == "admin" else 0,
                "last_updated": joined_at
            },
            "status": "active"
        }
        
        await users_collection.update_one(
            {"_id": user_id},
            {"$push": {"family_memberships": membership}},
            session=session
        )
    
    async def _check_rate_limit(self, request_context: Dict[str, Any], action: str, 
                              limit: int, window: int) -> None:
        """Check rate limit for family operations using security manager."""
        if not request_context or 'request' not in request_context:
            return  # Skip rate limiting if no request context
        
        try:
            await self.security_manager.check_rate_limit(
                request_context['request'], 
                action, 
                rate_limit_requests=limit,
                rate_limit_period=window
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
            "ttl": self._cache_ttl
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

    async def _validate_invitation_input(self, family_id: str, inviter_id: str, identifier: str, 
                                        relationship_type: str, identifier_type: str) -> None:
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
                field="identifier_type", value=identifier_type, constraint="valid_type"
            )
        
        if not relationship_type or relationship_type.lower() not in RELATIONSHIP_TYPES:
            raise InvalidRelationship(
                f"Invalid relationship type: {relationship_type}",
                relationship_type=relationship_type,
                valid_types=list(RELATIONSHIP_TYPES.keys())
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
                limit_type="family_members"
            )
    
    async def _find_and_validate_invitee(self, identifier: str, identifier_type: str) -> Dict[str, Any]:
        """Find and validate the invitee user by email or username."""
        if identifier_type == "email":
            invitee_user = await self._get_user_by_email(identifier.lower().strip())
            if not invitee_user:
                raise ValidationError(
                    f"User with email {identifier} not found", 
                    field="identifier", value=identifier, constraint="user_exists"
                )
        elif identifier_type == "username":
            invitee_user = await self._get_user_by_username(identifier.lower().strip())
            if not invitee_user:
                raise ValidationError(
                    f"User with username {identifier} not found", 
                    field="identifier", value=identifier, constraint="user_exists"
                )
        else:
            raise ValidationError(
                f"Invalid identifier type: {identifier_type}", 
                field="identifier_type", value=identifier_type, constraint="valid_type"
            )
        
        return invitee_user
    
    async def _check_existing_membership_and_invitations(self, invitee_id: str, family_id: str) -> None:
        """Check if user is already in family or has pending invitations."""
        # Check existing membership
        if await self._is_user_in_family(invitee_id, family_id):
            raise ValidationError(
                "User is already a member of this family", 
                field="invitee_id", value=invitee_id, constraint="not_already_member"
            )
        
        # Check for pending invitations
        invitations_collection = self.db_manager.get_collection("family_invitations")
        existing_invitation = await invitations_collection.find_one({
            "family_id": family_id,
            "invitee_user_id": invitee_id,
            "status": "pending",
            "expires_at": {"$gt": datetime.now(timezone.utc)}
        })
        
        if existing_invitation:
            raise ValidationError(
                "User already has a pending invitation to this family", 
                field="invitee_id", value=invitee_id, constraint="no_pending_invitation"
            )
    
    async def _validate_relationship_logic(self, inviter_id: str, invitee_id: str, 
                                         relationship_type: str, family_id: str) -> None:
        """Validate relationship logic to prevent contradictory relationships."""
        # Check if users already have a relationship in this family
        relationships_collection = self.db_manager.get_collection("family_relationships")
        existing_relationship = await relationships_collection.find_one({
            "family_id": family_id,
            "$or": [
                {"user_a_id": inviter_id, "user_b_id": invitee_id},
                {"user_a_id": invitee_id, "user_b_id": inviter_id}
            ],
            "status": "active"
        })
        
        if existing_relationship:
            raise ValidationError(
                "Users already have an existing relationship in this family", 
                field="relationship", constraint="no_existing_relationship"
            )
        
        # Additional logic validation (e.g., prevent someone from being both parent and child)
        # This can be extended based on business rules
    
    async def _generate_secure_invitation(self, family_id: str, inviter_id: str, 
                                        invitee_user: Dict[str, Any], relationship_type: str) -> Dict[str, Any]:
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
                "version": "1.0"
            }
        }
        
        return {
            "invitation_id": invitation_id,
            "document": invitation_document,
            "expires_at": expires_at,
            "token": invitation_token
        }
    
    async def _send_invitation_email_safe(self, invitation_doc: Dict[str, Any], family: Dict[str, Any]) -> bool:
        """Send invitation email with error handling that doesn't break transactions."""
        try:
            return await self._send_invitation_email(invitation_doc, family)
        except Exception as e:
            self.logger.warning(
                "Failed to send invitation email for %s: %s", 
                invitation_doc["invitation_id"], e,
                extra={
                    "invitation_id": invitation_doc["invitation_id"],
                    "invitee_email": invitation_doc["invitee_email"],
                    "family_id": invitation_doc["family_id"]
                }
            )
            return False

    async def _get_user_by_id(self, user_id: str) -> Dict[str, Any]:
        """Get user document by ID."""
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"_id": user_id})
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
        self.logger.warning(
            "Using legacy _create_virtual_sbd_account method. Consider using transactional version."
        )
        
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
                "audit_all_transactions": True
            },
            
            # Basic audit trail
            "audit_trail": {
                "created_by_system": "family_manager_legacy",
                "creation_timestamp": now,
                "last_activity": now,
                "activity_count": 0
            }
        }
        
        await users_collection.insert_one(virtual_account)
        
        # Log security event for virtual account creation
        await self._log_virtual_account_security_event(
            account_id=account_id,
            username=username,
            event_type="virtual_account_created",
            details={
                "family_id": family_id,
                "creation_method": "legacy",
                "transaction_safe": False
            }
        )
        self.logger.info("Virtual SBD account created: %s for family %s", username, family_id)

    async def _add_user_to_family_membership(self, user_id: str, family_id: str, role: str, joined_at: datetime) -> None:
        """Add user to family membership list."""
        users_collection = db_manager.get_collection("users")
        
        membership = {
            "family_id": family_id,
            "role": role,
            "joined_at": joined_at,
            "spending_permissions": {
                "can_spend": role == "admin",
                "spending_limit": -1 if role == "admin" else 0,
                "last_updated": joined_at
            }
        }
        
        await users_collection.update_one(
            {"_id": user_id},
            {"$push": {"family_memberships": membership}}
        )

    async def _create_bidirectional_relationship(self, family_id: str, user_a_id: str, user_b_id: str, 
                                               relationship_type: str) -> None:
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
            "updated_at": now
        }
        
        await relationships_collection.insert_one(relationship_doc)
        self.logger.info("Bidirectional relationship created: %s between %s and %s", 
                        relationship_id, user_a_id, user_b_id)

    async def _increment_family_member_count(self, family_id: str) -> None:
        """Increment family member count."""
        families_collection = db_manager.get_collection("families")
        await families_collection.update_one(
            {"family_id": family_id},
            {
                "$inc": {"member_count": 1},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )

    async def _get_sbd_account_balance(self, username: str) -> int:
        """Get SBD token balance for virtual account."""
        users_collection = db_manager.get_collection("users")
        account = await users_collection.find_one({"username": username}, {"sbd_tokens": 1})
        return account.get("sbd_tokens", 0) if account else 0

    async def validate_family_spending(self, family_username: str, spender_id: str, amount: int, 
                                     request_context: Dict[str, Any] = None) -> bool:
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
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # Verify this is a virtual family account with enhanced checks
            users_collection = self.db_manager.get_collection("users")
            virtual_account = await users_collection.find_one({
                "username": family_username,
                "is_virtual_account": True,
                "account_type": "family_virtual",
                "status": "active"
            })
            
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
                    family_username, spender_id, amount, "account_frozen", 
                    {**validation_context, "frozen_by": family["sbd_account"].get("frozen_by")}
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
                    family_username, spender_id, amount, "spending_limit_exceeded", 
                    {**validation_context, "spending_limit": spending_limit}
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
                        "validation_passed": True
                    }
                )
            
            # Log successful validation
            await self._log_spending_validation_success(
                family_username, spender_id, amount, validation_context
            )
            
            self.logger.debug(
                "Family spending validation passed for user %s, amount %d in account %s", 
                spender_id, amount, family_username,
                extra={
                    "family_username": family_username,
                    "spender_id": spender_id,
                    "amount": amount,
                    "spending_limit": spending_limit,
                    "family_id": family_id
                }
            )
            return True
            
        except Exception as e:
            await self._log_spending_validation_failure(
                family_username, spender_id, amount, "validation_error", 
                {**validation_context, "error": str(e)}
            )
            self.logger.error(
                "Error validating family spending: %s", e, 
                exc_info=True,
                extra=validation_context
            )
            return False

    async def _log_spending_validation_success(self, family_username: str, spender_id: str, 
                                             amount: int, context: Dict[str, Any]) -> None:
        """Log successful spending validation for audit purposes."""
        try:
            users_collection = self.db_manager.get_collection("users")
            virtual_account = await users_collection.find_one({
                "username": family_username,
                "is_virtual_account": True
            })
            
            if virtual_account:
                await self._log_virtual_account_security_event(
                    account_id=virtual_account.get("account_id"),
                    username=family_username,
                    event_type="spending_validation_success",
                    details={
                        "spender_id": spender_id,
                        "amount": amount,
                        "context": context
                    }
                )
        except Exception as e:
            self.logger.error("Failed to log spending validation success: %s", e, exc_info=True)

    async def _log_spending_validation_failure(self, family_username: str, spender_id: str, 
                                             amount: int, reason: str, context: Dict[str, Any]) -> None:
        """Log failed spending validation for security monitoring."""
        try:
            users_collection = self.db_manager.get_collection("users")
            virtual_account = await users_collection.find_one({
                "username": family_username,
                "is_virtual_account": True
            })
            
            if virtual_account:
                await self._log_virtual_account_security_event(
                    account_id=virtual_account.get("account_id"),
                    username=family_username,
                    event_type="spending_validation_failure",
                    details={
                        "spender_id": spender_id,
                        "amount": amount,
                        "reason": reason,
                        "context": context
                    }
                )
            
            # Also log to application logs for immediate monitoring
            self.logger.warning(
                "Family spending validation failed: %s for user %s, amount %d, reason: %s",
                family_username, spender_id, amount, reason,
                extra={
                    "family_username": family_username,
                    "spender_id": spender_id,
                    "amount": amount,
                    "reason": reason,
                    "context": context
                }
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
                membership.get("family_id") == family_id and 
                membership.get("status") == "active"
                for membership in family_memberships
            )
        except Exception as e:
            self.logger.error("Error checking family membership: %s", e, exc_info=True)
            return False

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
            account = await users_collection.find_one({
                "username": username,
                "is_virtual_account": True,
                "account_type": "family_virtual",
                "status": "active"
            })
            return account is not None
        except Exception as e:
            self.logger.error("Error checking if account is virtual family account: %s", e, exc_info=True)
            return False

    async def validate_username_against_reserved_prefixes(self, username: str) -> Tuple[bool, str]:
        """
        Validate username against reserved prefixes with comprehensive checking.
        
        Args:
            username: Username to validate
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if not username or not isinstance(username, str):
            return False, "Username must be a non-empty string"
        
        username_lower = username.lower().strip()
        
        # Check against all reserved prefixes
        for prefix in RESERVED_PREFIXES:
            if username_lower.startswith(prefix):
                return False, f"Username cannot start with '{prefix}' - this prefix is reserved for system accounts"
        
        # Additional validation for potential conflicts
        if username_lower in ["family", "team", "admin", "system", "bot", "service", "root", "api"]:
            return False, "Username conflicts with reserved system names"
        
        # Check for numeric-only usernames that could conflict with IDs
        if username_lower.isdigit():
            return False, "Username cannot be numeric only"
        
        # Check minimum and maximum length
        if len(username) < 3:
            return False, "Username must be at least 3 characters long"
        
        if len(username) > 30:
            return False, "Username cannot exceed 30 characters"
        
        return True, ""

    async def generate_collision_resistant_family_username(self, family_name: str, max_attempts: int = 10) -> str:
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
        
        for attempt in range(max_attempts):
            candidate_username = base_username
            
            # Add suffix for collision avoidance after first attempt
            if attempt > 0:
                # Use timestamp-based suffix for uniqueness
                timestamp_suffix = str(int(datetime.now(timezone.utc).timestamp()))[-6:]
                candidate_username = f"{base_username}_{timestamp_suffix}"
            
            # Check if username is available
            if await self._is_username_available(candidate_username):
                # Validate against reserved prefixes (should pass since we're using family_ prefix)
                is_valid, error_msg = await self.validate_username_against_reserved_prefixes(candidate_username)
                if is_valid:
                    self.logger.info(
                        "Generated collision-resistant family username: %s (attempt %d)", 
                        candidate_username, attempt + 1
                    )
                    return candidate_username
                else:
                    self.logger.warning(
                        "Generated username failed validation: %s - %s", 
                        candidate_username, error_msg
                    )
        
        # If we can't generate a unique username, raise an error
        raise ValidationError(
            f"Unable to generate unique family username after {max_attempts} attempts",
            field="family_name",
            value=family_name,
            constraint="uniqueness"
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
        sanitized = re.sub(r'[^a-z0-9_]', '_', sanitized)
        
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        
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
                invitation["expires_at"].strftime('%Y-%m-%d %H:%M:%S UTC')
            )
            
            if not success:
                self.logger.warning("Failed to send invitation email to %s", invitation["invitee_email"])
            else:
                self.logger.info("Invitation email sent successfully to %s", invitation["invitee_email"])
                
        except Exception as e:
            self.logger.error("Error sending invitation email: %s", e, exc_info=True)
            # Don't raise exception - invitation was created successfully

    async def delete_family(self, family_id: str, admin_user_id: str) -> Dict[str, Any]:
        """
        Delete a family and clean up all associated resources.
        
        Args:
            family_id: ID of the family to delete
            admin_user_id: ID of the admin user requesting deletion
            
        Returns:
            Dict containing deletion confirmation
            
        Raises:
            FamilyNotFound: If family doesn't exist
            InsufficientPermissions: If user is not admin
            FamilyError: If deletion fails
        """
        start_time = db_manager.log_query_start("families", "delete_family", 
                                              {"family_id": family_id, "admin_user_id": admin_user_id})
        
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
            await self._delete_family_relationships(family_id)
            
            # Delete all family invitations
            await self._delete_family_invitations(family_id)
            
            # Delete all family notifications
            await self._delete_family_notifications(family_id)
            
            # Delete all family token requests
            await self._delete_family_token_requests(family_id)
            
            # Finally, delete the family document
            families_collection = db_manager.get_collection("families")
            await families_collection.delete_one({"family_id": family_id})
            
            db_manager.log_query_success("families", "delete_family", start_time, 1,
                                       f"Family deleted: {family_id}")
            
            self.logger.info("Family deleted successfully: %s by admin %s", family_id, admin_user_id)
            
            return {
                "status": "success",
                "family_id": family_id,
                "message": "Family and all associated resources have been deleted",
                "members_affected": len(member_ids)
            }
            
        except (FamilyNotFound, InsufficientPermissions):
            db_manager.log_query_error("families", "delete_family", start_time,
                                     Exception("Validation error"), {"family_id": family_id})
            raise
        except Exception as e:
            db_manager.log_query_error("families", "delete_family", start_time, e,
                                     {"family_id": family_id})
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
            virtual_account = await users_collection.find_one({
                "username": username,
                "is_virtual_account": True,
                "managed_by_family": family_id
            })
            
            if virtual_account:
                remaining_balance = virtual_account.get("sbd_tokens", 0)
                transaction_count = len(virtual_account.get("sbd_tokens_transactions", []))
                
                # Log the cleanup for audit purposes
                self.logger.info(
                    "Cleaning up virtual SBD account: %s for family %s. "
                    "Remaining balance: %d tokens, Transaction count: %d",
                    username, family_id, remaining_balance, transaction_count
                )
                
                # Delete the virtual account
                result = await users_collection.delete_one({
                    "username": username,
                    "is_virtual_account": True,
                    "managed_by_family": family_id
                })
                
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
                {"_id": {"$in": member_ids}},
                {"$pull": {"family_memberships": {"family_id": family_id}}}
            )
            
            self.logger.info("Removed family memberships for %d users from family %s", 
                           result.modified_count, family_id)
            
        except Exception as e:
            self.logger.error("Error removing family memberships for family %s: %s", family_id, e, exc_info=True)

    async def _delete_family_relationships(self, family_id: str) -> None:
        """Delete all relationships for a family."""
        try:
            relationships_collection = db_manager.get_collection("family_relationships")
            result = await relationships_collection.delete_many({"family_id": family_id})
            
            self.logger.info("Deleted %d family relationships for family %s", 
                           result.deleted_count, family_id)
            
        except Exception as e:
            self.logger.error("Error deleting family relationships for family %s: %s", family_id, e, exc_info=True)

    async def _delete_family_invitations(self, family_id: str) -> None:
        """Delete all invitations for a family."""
        try:
            invitations_collection = db_manager.get_collection("family_invitations")
            result = await invitations_collection.delete_many({"family_id": family_id})
            
            self.logger.info("Deleted %d family invitations for family %s", 
                           result.deleted_count, family_id)
            
        except Exception as e:
            self.logger.error("Error deleting family invitations for family %s: %s", family_id, e, exc_info=True)

    async def _delete_family_notifications(self, family_id: str) -> None:
        """Delete all notifications for a family."""
        try:
            notifications_collection = db_manager.get_collection("family_notifications")
            result = await notifications_collection.delete_many({"family_id": family_id})
            
            self.logger.info("Deleted %d family notifications for family %s", 
                           result.deleted_count, family_id)
            
        except Exception as e:
            self.logger.error("Error deleting family notifications for family %s: %s", family_id, e, exc_info=True)

    async def _delete_family_token_requests(self, family_id: str) -> None:
        """Delete all token requests for a family."""
        try:
            requests_collection = db_manager.get_collection("family_token_requests")
            result = await requests_collection.delete_many({"family_id": family_id})
            
            self.logger.info("Deleted %d family token requests for family %s", 
                           result.deleted_count, family_id)
            
        except Exception as e:
            self.logger.error("Error deleting family token requests for family %s: %s", family_id, e, exc_info=True)

    async def _log_virtual_account_security_event(self, account_id: str, username: str, event_type: str, 
                                                 details: Dict[str, Any], session: ClientSession = None) -> None:
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
                "severity": self._get_event_severity(event_type)
            }
            
            # Store in virtual account audit trail
            users_collection = self.db_manager.get_collection("users")
            update_query = {
                "$push": {"audit_trail.security_events": security_event},
                "$set": {"audit_trail.last_activity": security_event["timestamp"]},
                "$inc": {"audit_trail.activity_count": 1}
            }
            
            if session:
                await users_collection.update_one(
                    {"username": username, "is_virtual_account": True},
                    update_query,
                    session=session
                )
            else:
                await users_collection.update_one(
                    {"username": username, "is_virtual_account": True},
                    update_query
                )
            
            # Also log to application logs for monitoring
            self.logger.info(
                "Virtual account security event: %s for %s (%s)",
                event_type, username, account_id,
                extra={
                    "event_id": security_event["event_id"],
                    "account_id": account_id,
                    "username": username,
                    "event_type": event_type,
                    "severity": security_event["severity"],
                    "details": details
                }
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to log virtual account security event: %s", e,
                exc_info=True,
                extra={
                    "account_id": account_id,
                    "username": username,
                    "event_type": event_type
                }
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
            "suspicious_transaction"
        ]
        
        medium_severity_events = [
            "virtual_account_created",
            "permissions_updated",
            "large_transaction",
            "account_unfrozen"
        ]
        
        if event_type in high_severity_events:
            return "high"
        elif event_type in medium_severity_events:
            return "medium"
        else:
            return "low"

    async def cleanup_virtual_account(self, family_id: str, admin_user_id: str, 
                                    retention_override: bool = False) -> Dict[str, Any]:
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
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        start_time = self.db_manager.log_query_start("users", "cleanup_virtual_account", operation_context)
        
        try:
            # Verify family exists and user has admin permissions
            family = await self._get_family_by_id(family_id)
            if admin_user_id not in family["admin_user_ids"]:
                raise InsufficientPermissions(
                    "Only family admins can cleanup virtual accounts",
                    required_role="admin",
                    user_role="member"
                )
            
            # Get virtual account
            virtual_username = family["sbd_account"]["account_username"]
            users_collection = self.db_manager.get_collection("users")
            virtual_account = await users_collection.find_one({
                "username": virtual_username,
                "is_virtual_account": True,
                "managed_by_family": family_id
            })
            
            if not virtual_account:
                raise ValidationError(
                    "Virtual account not found for family",
                    field="family_id",
                    value=family_id
                )
            
            now = datetime.now(timezone.utc)
            cleanup_results = {
                "account_id": virtual_account.get("account_id"),
                "username": virtual_username,
                "family_id": family_id,
                "cleanup_timestamp": now,
                "admin_user_id": admin_user_id,
                "retention_override": retention_override
            }
            
            # Check if account has remaining balance
            remaining_balance = virtual_account.get("sbd_tokens", 0)
            if remaining_balance > 0:
                cleanup_results["remaining_balance"] = remaining_balance
                cleanup_results["balance_transferred"] = False
                
                # Log warning about remaining balance
                self.logger.warning(
                    "Virtual account cleanup with remaining balance: %s tokens in %s",
                    remaining_balance, virtual_username
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
                        "performance_metrics": virtual_account.get("performance_metrics", {})
                    }
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
                            "sbd_tokens_transactions": []  # Clear transactions (retained in cleanup_data)
                        }
                    }
                )
                
                cleanup_results["cleanup_method"] = "immediate"
                cleanup_results["data_retained"] = True
                
            else:
                # Schedule for future cleanup based on retention policy
                retention_days = virtual_account.get("retention_policy", {}).get("retention_period_days", VIRTUAL_ACCOUNT_RETENTION_DAYS)
                cleanup_date = now + timedelta(days=retention_days)
                
                await users_collection.update_one(
                    {"username": virtual_username, "is_virtual_account": True},
                    {
                        "$set": {
                            "status": "scheduled_for_cleanup",
                            "cleanup_scheduled_at": now,
                            "cleanup_scheduled_by": admin_user_id,
                            "cleanup_date": cleanup_date,
                            "retention_policy.cleanup_scheduled": True
                        }
                    }
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
                    "remaining_balance": remaining_balance
                }
            )
            
            self.db_manager.log_query_success(
                "users", "cleanup_virtual_account", start_time, 1,
                f"Virtual account cleanup initiated: {virtual_username}"
            )
            
            self.logger.info(
                "Virtual account cleanup initiated: %s for family %s by admin %s",
                virtual_username, family_id, admin_user_id,
                extra=cleanup_results
            )
            
            return cleanup_results
            
        except (FamilyNotFound, InsufficientPermissions, ValidationError) as e:
            self.db_manager.log_query_error("users", "cleanup_virtual_account", start_time, e, operation_context)
            raise
            
        except Exception as e:
            self.db_manager.log_query_error("users", "cleanup_virtual_account", start_time, e, operation_context)
            self.logger.error(
                "Failed to cleanup virtual account for family %s: %s", family_id, e,
                exc_info=True,
                extra=operation_context
            )
            raise TransactionError(
                f"Failed to cleanup virtual account: {str(e)}",
                operation="cleanup_virtual_account"
            )

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
            
            # Validate security context using family security manager
            security_result = await family_security_manager.validate_user_security_context(
                user_id=user_id,
                request=request,
                operation=operation,
                require_2fa=operation in ["create_family", "remove_member", "promote_admin"],
                temp_token=request_context.get("temp_token")
            )
            
            self.logger.debug(
                "Security context validation successful for user %s, operation: %s",
                user_id, operation
            )
            
            return security_result["validated"]
            
        except Exception as e:
            self.logger.error(
                "Security context validation failed for user %s: %s",
                user_id, str(e), exc_info=True
            )
            raise FamilyError(
                f"Security validation failed: {str(e)}",
                error_code="SECURITY_VALIDATION_FAILED"
            )

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
                        bypass.get("ip_address") == ip_address and 
                        bypass.get("expires_at", "") > current_time
                        for bypass in temp_bypasses
                    )
                    
                    if not ip_allowed:
                        self.logger.warning(
                            "Untrusted IP access attempt for user %s from %s",
                            user_id, ip_address
                        )
                        return False
            
            # Check User Agent lockdown
            if user.get("trusted_user_agent_lockdown", False):
                trusted_user_agents = user.get("trusted_user_agents", [])
                if user_agent not in trusted_user_agents:
                    # Check for temporary User Agent bypasses
                    temp_bypasses = user.get("temporary_user_agent_bypasses", [])
                    current_time = datetime.now(timezone.utc).isoformat()
                    
                    ua_allowed = any(
                        bypass.get("user_agent") == user_agent and 
                        bypass.get("expires_at", "") > current_time
                        for bypass in temp_bypasses
                    )
                    
                    if not ua_allowed:
                        self.logger.warning(
                            "Untrusted User Agent access attempt for user %s: %s",
                            user_id, user_agent
                        )
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Error checking trusted access for user %s: %s",
                user_id, str(e), exc_info=True
            )
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
            # Import here to avoid circular imports
            from second_brain_database.routes.family.security import family_security_manager
            
            # Extract security context
            ip_address = context.get("ip_address")
            success = context.get("success", True)
            
            # Log using family security manager
            await family_security_manager.log_family_security_event(
                user_id=user_id,
                action=action,
                context=context,
                success=success,
                ip_address=ip_address
            )
            
            self.logger.debug(
                "Family security event logged: %s by user %s",
                action, user_id
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to log family security event: %s", str(e),
                exc_info=True
            )

    async def _check_rate_limit(self, request_context: Dict[str, Any], action: str, limit: int, period: int) -> None:
        """Check rate limit for family operations using security manager."""
        try:
            request = request_context.get("request")
            if not request:
                return  # Skip rate limiting if no request context
            
            # Use family security manager for rate limiting
            from second_brain_database.routes.family.security import family_security_manager
            
            await family_security_manager.check_family_operation_rate_limit(
                request=request,
                operation=action,
                user_id=request_context.get("user_id")
            )
            
        except Exception as e:
            self.logger.warning(
                "Rate limit check failed for action %s: %s",
                action, str(e)
            )
            raise RateLimitExceeded(
                f"Rate limit exceeded for {action}",
                action=action,
                limit=limit,
                window=period
            )


# Global family manager instance with dependency injection
family_manager = FamilyManager(
    db_manager=db_manager,
    email_manager=email_manager,
    security_manager=security_manager,
    redis_manager=redis_manager
)