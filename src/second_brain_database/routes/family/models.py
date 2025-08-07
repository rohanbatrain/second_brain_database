"""Family management models for user relationships and shared resources."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, field_validator

from second_brain_database.docs.models import BaseDocumentedModel
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Family Models]")

# Constants for validation
FAMILY_NAME_MIN_LENGTH: int = 3
FAMILY_NAME_MAX_LENGTH: int = 50
RELATIONSHIP_DESCRIPTION_MAX_LENGTH: int = 255
TOKEN_REQUEST_REASON_MAX_LENGTH: int = 500
NOTIFICATION_MESSAGE_MAX_LENGTH: int = 1000

# Relationship types mapping
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

# Notification types
class NotificationType(str, Enum):
    """Enumeration of family notification types."""
    SBD_SPEND = "sbd_spend"
    SBD_DEPOSIT = "sbd_deposit"
    LARGE_TRANSACTION = "large_transaction"
    SPENDING_LIMIT_REACHED = "spending_limit_reached"
    ACCOUNT_FROZEN = "account_frozen"
    ACCOUNT_UNFROZEN = "account_unfrozen"
    ADMIN_PROMOTED = "admin_promoted"
    ADMIN_DEMOTED = "admin_demoted"
    MEMBER_ADDED = "member_added"
    MEMBER_REMOVED = "member_removed"
    TOKEN_REQUEST_CREATED = "token_request_created"
    TOKEN_REQUEST_APPROVED = "token_request_approved"
    TOKEN_REQUEST_DENIED = "token_request_denied"
    PERMISSIONS_UPDATED = "permissions_updated"

# Status enums
class InvitationStatus(str, Enum):
    """Enumeration of invitation statuses."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"

class RelationshipStatus(str, Enum):
    """Enumeration of relationship statuses."""
    ACTIVE = "active"
    PENDING = "pending"
    DECLINED = "declined"

class TokenRequestStatus(str, Enum):
    """Enumeration of token request statuses."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    AUTO_APPROVED = "auto_approved"

class NotificationStatus(str, Enum):
    """Enumeration of notification statuses."""
    PENDING = "pending"
    SENT = "sent"
    READ = "read"
    ARCHIVED = "archived"

# Request Models
class CreateFamilyRequest(BaseDocumentedModel):
    """
    Request model for creating a new family.
    
    The family name is optional and will be auto-generated if not provided.
    The requesting user automatically becomes the family administrator.
    """
    
    name: Optional[str] = Field(
        None,
        min_length=FAMILY_NAME_MIN_LENGTH,
        max_length=FAMILY_NAME_MAX_LENGTH,
        description="Optional custom family name. If not provided, will be auto-generated.",
        example="Smith Family"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Smith Family"
            }
        }
    }

class InviteMemberRequest(BaseDocumentedModel):
    """
    Request model for inviting a family member.
    
    Requires the invitee's email and the relationship type from the inviter's perspective.
    """
    
    email: EmailStr = Field(
        ...,
        description="Email address of the user to invite to the family",
        example="john.doe@example.com"
    )
    relationship_type: str = Field(
        ...,
        description="Relationship type from inviter's perspective (e.g., 'child', 'parent', 'sibling')",
        example="child"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "john.doe@example.com",
                "relationship_type": "child"
            }
        }
    }
    
    @field_validator("relationship_type")
    @classmethod
    def validate_relationship_type(cls, v: str) -> str:
        """Validate that the relationship type is supported."""
        if v.lower() not in RELATIONSHIP_TYPES:
            logger.error("Invalid relationship type: %s", v)
            raise ValueError(f"Relationship type must be one of: {list(RELATIONSHIP_TYPES.keys())}")
        return v.lower()

class RespondToInvitationRequest(BaseDocumentedModel):
    """
    Request model for responding to a family invitation.
    """
    
    action: str = Field(
        ...,
        description="Action to take on the invitation: 'accept' or 'decline'",
        example="accept"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "action": "accept"
            }
        }
    }
    
    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate that the action is either accept or decline."""
        if v.lower() not in ["accept", "decline"]:
            logger.error("Invalid invitation action: %s", v)
            raise ValueError("Action must be either 'accept' or 'decline'")
        return v.lower()

class UpdateRelationshipRequest(BaseDocumentedModel):
    """
    Request model for updating a family relationship.
    """
    
    relationship_type_a_to_b: str = Field(
        ...,
        description="Relationship type from user A to user B",
        example="parent"
    )
    relationship_type_b_to_a: str = Field(
        ...,
        description="Relationship type from user B to user A",
        example="child"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "relationship_type_a_to_b": "parent",
                "relationship_type_b_to_a": "child"
            }
        }
    }

class UpdateSpendingPermissionsRequest(BaseDocumentedModel):
    """
    Request model for updating family member spending permissions.
    """
    
    user_id: str = Field(
        ...,
        description="User ID of the family member to update permissions for",
        example="507f1f77bcf86cd799439011"
    )
    spending_limit: int = Field(
        ...,
        description="Spending limit in SBD tokens. Use -1 for unlimited spending.",
        example=1000
    )
    can_spend: bool = Field(
        ...,
        description="Whether the user can spend from the family account",
        example=True
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "spending_limit": 1000,
                "can_spend": True
            }
        }
    }

class FreezeAccountRequest(BaseDocumentedModel):
    """
    Request model for freezing or unfreezing the family SBD account.
    """
    
    action: str = Field(
        ...,
        description="Action to take: 'freeze' or 'unfreeze'",
        example="freeze"
    )
    reason: Optional[str] = Field(
        None,
        max_length=RELATIONSHIP_DESCRIPTION_MAX_LENGTH,
        description="Optional reason for the freeze action",
        example="Suspicious activity detected"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "action": "freeze",
                "reason": "Suspicious activity detected"
            }
        }
    }
    
    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate that the action is either freeze or unfreeze."""
        if v.lower() not in ["freeze", "unfreeze"]:
            logger.error("Invalid freeze action: %s", v)
            raise ValueError("Action must be either 'freeze' or 'unfreeze'")
        return v.lower()

class CreateTokenRequestRequest(BaseDocumentedModel):
    """
    Request model for creating a token request from the family account.
    """
    
    amount: int = Field(
        ...,
        gt=0,
        description="Amount of SBD tokens to request",
        example=500
    )
    reason: str = Field(
        ...,
        max_length=TOKEN_REQUEST_REASON_MAX_LENGTH,
        description="Reason for the token request",
        example="Need tokens for school supplies"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "amount": 500,
                "reason": "Need tokens for school supplies"
            }
        }
    }

class ReviewTokenRequestRequest(BaseDocumentedModel):
    """
    Request model for reviewing a token request (admin only).
    """
    
    action: str = Field(
        ...,
        description="Action to take: 'approve' or 'deny'",
        example="approve"
    )
    comments: Optional[str] = Field(
        None,
        max_length=TOKEN_REQUEST_REASON_MAX_LENGTH,
        description="Optional comments from the admin",
        example="Approved for educational expenses"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "action": "approve",
                "comments": "Approved for educational expenses"
            }
        }
    }
    
    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate that the action is either approve or deny."""
        if v.lower() not in ["approve", "deny"]:
            logger.error("Invalid review action: %s", v)
            raise ValueError("Action must be either 'approve' or 'deny'")
        return v.lower()

class AdminActionRequest(BaseDocumentedModel):
    """
    Request model for admin actions (promote/demote).
    """
    
    action: str = Field(
        ...,
        description="Action to take: 'promote' or 'demote'",
        example="promote"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "action": "promote"
            }
        }
    }
    
    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate that the action is either promote or demote."""
        if v.lower() not in ["promote", "demote"]:
            logger.error("Invalid admin action: %s", v)
            raise ValueError("Action must be either 'promote' or 'demote'")
        return v.lower()

# Response Models
class FamilyResponse(BaseDocumentedModel):
    """
    Response model for family information.
    
    Contains comprehensive family details including member count,
    SBD account information, and user's role in the family.
    """
    
    family_id: str = Field(
        ...,
        description="Unique family identifier",
        example="fam_1234567890abcdef"
    )
    name: str = Field(
        ...,
        description="Family name",
        example="Smith Family"
    )
    admin_user_ids: List[str] = Field(
        ...,
        description="List of user IDs who are family administrators",
        example=["507f1f77bcf86cd799439011"]
    )
    member_count: int = Field(
        ...,
        description="Total number of family members",
        example=4
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the family was created",
        example="2024-01-01T12:00:00Z"
    )
    is_admin: bool = Field(
        ...,
        description="Whether the current user is an admin of this family",
        example=True
    )
    sbd_account: Dict[str, Any] = Field(
        ...,
        description="Family SBD account information including balance and permissions",
        example={
            "account_username": "family_smith",
            "balance": 5000,
            "is_frozen": False,
            "spending_permissions": {}
        }
    )
    usage_stats: Dict[str, Any] = Field(
        ...,
        description="Family usage statistics and limits",
        example={
            "current_members": 4,
            "max_members_allowed": 10,
            "can_add_members": True
        }
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "family_id": "fam_1234567890abcdef",
                "name": "Smith Family",
                "admin_user_ids": ["507f1f77bcf86cd799439011"],
                "member_count": 4,
                "created_at": "2024-01-01T12:00:00Z",
                "is_admin": True,
                "sbd_account": {
                    "account_username": "family_smith",
                    "balance": 5000,
                    "is_frozen": False,
                    "spending_permissions": {}
                },
                "usage_stats": {
                    "current_members": 4,
                    "max_members_allowed": 10,
                    "can_add_members": True
                }
            }
        }
    }

class FamilyMemberResponse(BaseDocumentedModel):
    """
    Response model for family member information.
    """
    
    user_id: str = Field(
        ...,
        description="User ID of the family member",
        example="507f1f77bcf86cd799439011"
    )
    username: str = Field(
        ...,
        description="Username of the family member",
        example="john_doe"
    )
    email: str = Field(
        ...,
        description="Email address of the family member",
        example="john.doe@example.com"
    )
    relationship_type: str = Field(
        ...,
        description="Relationship type from current user's perspective",
        example="child"
    )
    role: str = Field(
        ...,
        description="Role in the family: 'admin' or 'member'",
        example="member"
    )
    joined_at: datetime = Field(
        ...,
        description="UTC timestamp when the member joined the family",
        example="2024-01-01T12:30:00Z"
    )
    spending_permissions: Dict[str, Any] = Field(
        ...,
        description="SBD spending permissions for this member",
        example={
            "can_spend": True,
            "spending_limit": 1000,
            "last_updated": "2024-01-01T12:00:00Z"
        }
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "username": "john_doe",
                "email": "john.doe@example.com",
                "relationship_type": "child",
                "role": "member",
                "joined_at": "2024-01-01T12:30:00Z",
                "spending_permissions": {
                    "can_spend": True,
                    "spending_limit": 1000,
                    "last_updated": "2024-01-01T12:00:00Z"
                }
            }
        }
    }

class InvitationResponse(BaseDocumentedModel):
    """
    Response model for family invitation information.
    """
    
    invitation_id: str = Field(
        ...,
        description="Unique invitation identifier",
        example="inv_1234567890abcdef"
    )
    family_name: str = Field(
        ...,
        description="Name of the family the user is invited to",
        example="Smith Family"
    )
    inviter_username: str = Field(
        ...,
        description="Username of the person who sent the invitation",
        example="jane_smith"
    )
    relationship_type: str = Field(
        ...,
        description="Proposed relationship type",
        example="child"
    )
    status: InvitationStatus = Field(
        ...,
        description="Current status of the invitation",
        example=InvitationStatus.PENDING
    )
    expires_at: datetime = Field(
        ...,
        description="UTC timestamp when the invitation expires",
        example="2024-01-08T12:00:00Z"
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the invitation was created",
        example="2024-01-01T12:00:00Z"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "invitation_id": "inv_1234567890abcdef",
                "family_name": "Smith Family",
                "inviter_username": "jane_smith",
                "relationship_type": "child",
                "status": "pending",
                "expires_at": "2024-01-08T12:00:00Z",
                "created_at": "2024-01-01T12:00:00Z"
            }
        }
    }

class SBDAccountResponse(BaseDocumentedModel):
    """
    Response model for family SBD account information.
    """
    
    account_username: str = Field(
        ...,
        description="Virtual account username for the family",
        example="family_smith"
    )
    balance: int = Field(
        ...,
        description="Current SBD token balance",
        example=5000
    )
    is_frozen: bool = Field(
        ...,
        description="Whether the account is currently frozen",
        example=False
    )
    frozen_by: Optional[str] = Field(
        None,
        description="Username of admin who froze the account",
        example=None
    )
    spending_permissions: Dict[str, Any] = Field(
        ...,
        description="Spending permissions for all family members",
        example={
            "507f1f77bcf86cd799439011": {
                "can_spend": True,
                "spending_limit": 1000,
                "updated_by": "jane_smith",
                "updated_at": "2024-01-01T12:00:00Z"
            }
        }
    )
    recent_transactions: List[Dict[str, Any]] = Field(
        ...,
        description="Recent SBD token transactions",
        example=[
            {
                "type": "spend",
                "amount": 100,
                "from_user": "john_doe",
                "to_user": "shop_system",
                "timestamp": "2024-01-01T15:00:00Z",
                "transaction_id": "txn_1234567890"
            }
        ]
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "account_username": "family_smith",
                "balance": 5000,
                "is_frozen": False,
                "frozen_by": None,
                "spending_permissions": {
                    "507f1f77bcf86cd799439011": {
                        "can_spend": True,
                        "spending_limit": 1000,
                        "updated_by": "jane_smith",
                        "updated_at": "2024-01-01T12:00:00Z"
                    }
                },
                "recent_transactions": [
                    {
                        "type": "spend",
                        "amount": 100,
                        "from_user": "john_doe",
                        "to_user": "shop_system",
                        "timestamp": "2024-01-01T15:00:00Z",
                        "transaction_id": "txn_1234567890"
                    }
                ]
            }
        }
    }

class TokenRequestResponse(BaseDocumentedModel):
    """
    Response model for token request information.
    """
    
    request_id: str = Field(
        ...,
        description="Unique token request identifier",
        example="req_1234567890abcdef"
    )
    requester_username: str = Field(
        ...,
        description="Username of the person who made the request",
        example="john_doe"
    )
    amount: int = Field(
        ...,
        description="Amount of SBD tokens requested",
        example=500
    )
    reason: str = Field(
        ...,
        description="Reason provided for the token request",
        example="Need tokens for school supplies"
    )
    status: TokenRequestStatus = Field(
        ...,
        description="Current status of the request",
        example=TokenRequestStatus.PENDING
    )
    auto_approved: bool = Field(
        ...,
        description="Whether the request was automatically approved",
        example=False
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the request was created",
        example="2024-01-01T12:00:00Z"
    )
    expires_at: datetime = Field(
        ...,
        description="UTC timestamp when the request expires",
        example="2024-01-08T12:00:00Z"
    )
    admin_comments: Optional[str] = Field(
        None,
        description="Comments from the admin who reviewed the request",
        example="Approved for educational expenses"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "request_id": "req_1234567890abcdef",
                "requester_username": "john_doe",
                "amount": 500,
                "reason": "Need tokens for school supplies",
                "status": "pending",
                "auto_approved": False,
                "created_at": "2024-01-01T12:00:00Z",
                "expires_at": "2024-01-08T12:00:00Z",
                "admin_comments": None
            }
        }
    }

class NotificationResponse(BaseDocumentedModel):
    """
    Response model for family notification information.
    """
    
    notification_id: str = Field(
        ...,
        description="Unique notification identifier",
        example="not_1234567890abcdef"
    )
    type: NotificationType = Field(
        ...,
        description="Type of notification",
        example=NotificationType.SBD_SPEND
    )
    title: str = Field(
        ...,
        description="Notification title",
        example="SBD Token Spending"
    )
    message: str = Field(
        ...,
        description="Notification message content",
        example="John spent 100 SBD tokens at the shop"
    )
    data: Dict[str, Any] = Field(
        ...,
        description="Additional notification data",
        example={
            "transaction_id": "txn_1234567890",
            "amount": 100,
            "from_user": "john_doe",
            "to_user": "shop_system"
        }
    )
    status: NotificationStatus = Field(
        ...,
        description="Current notification status",
        example=NotificationStatus.SENT
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the notification was created",
        example="2024-01-01T15:00:00Z"
    )
    is_read: bool = Field(
        ...,
        description="Whether the current user has read this notification",
        example=False
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "notification_id": "not_1234567890abcdef",
                "type": "sbd_spend",
                "title": "SBD Token Spending",
                "message": "John spent 100 SBD tokens at the shop",
                "data": {
                    "transaction_id": "txn_1234567890",
                    "amount": 100,
                    "from_user": "john_doe",
                    "to_user": "shop_system"
                },
                "status": "sent",
                "created_at": "2024-01-01T15:00:00Z",
                "is_read": False
            }
        }
    }

class FamilyLimitsResponse(BaseDocumentedModel):
    """
    Response model for family limits and usage information.
    """
    
    max_families_allowed: int = Field(
        ...,
        description="Maximum number of families the user can create or join",
        example=1
    )
    max_members_per_family: int = Field(
        ...,
        description="Maximum number of members per family for families where user is admin",
        example=5
    )
    current_families: int = Field(
        ...,
        description="Current number of families the user belongs to",
        example=1
    )
    families_usage: List[Dict[str, Any]] = Field(
        ...,
        description="Usage details for each family",
        example=[
            {
                "family_id": "fam_1234567890abcdef",
                "name": "Smith Family",
                "member_count": 4,
                "is_admin": True
            }
        ]
    )
    can_create_family: bool = Field(
        ...,
        description="Whether the user can create a new family",
        example=False
    )
    upgrade_required: bool = Field(
        ...,
        description="Whether an upgrade is required to increase limits",
        example=True
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "max_families_allowed": 1,
                "max_members_per_family": 5,
                "current_families": 1,
                "families_usage": [
                    {
                        "family_id": "fam_1234567890abcdef",
                        "name": "Smith Family",
                        "member_count": 4,
                        "is_admin": True
                    }
                ],
                "can_create_family": False,
                "upgrade_required": True
            }
        }
    }

# Database Document Models
class FamilyDocument(BaseModel):
    """
    Database document model for families collection.
    
    Represents the complete family document structure stored in MongoDB.
    """
    
    family_id: str = Field(..., description="Unique family identifier")
    name: str = Field(..., description="Family name")
    admin_user_ids: List[str] = Field(..., description="List of admin user IDs")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    member_count: int = Field(default=1, description="Cached member count")
    is_active: bool = Field(default=True, description="Soft delete flag")
    
    # SBD account information
    sbd_account: Dict[str, Any] = Field(
        default_factory=lambda: {
            "account_username": "",
            "is_frozen": False,
            "frozen_by": None,
            "frozen_at": None,
            "spending_permissions": {},
            "notification_settings": {
                "notify_on_spend": True,
                "notify_on_deposit": True,
                "large_transaction_threshold": 1000,
                "notify_admins_only": False
            }
        },
        description="SBD account configuration"
    )
    
    # Family settings
    settings: Dict[str, Any] = Field(
        default_factory=lambda: {
            "allow_member_invites": False,
            "visibility": "private",
            "auto_approval_threshold": 100,
            "request_expiry_hours": 168  # 7 days
        },
        description="Family configuration settings"
    )
    
    # Succession planning
    succession_plan: Dict[str, Any] = Field(
        default_factory=lambda: {
            "backup_admins": [],
            "recovery_contacts": []
        },
        description="Admin succession and recovery configuration"
    )

class FamilyRelationshipDocument(BaseModel):
    """
    Database document model for family_relationships collection.
    """
    
    relationship_id: str = Field(..., description="Unique relationship identifier")
    family_id: str = Field(..., description="Reference to family")
    user_a_id: str = Field(..., description="First user in relationship")
    user_b_id: str = Field(..., description="Second user in relationship")
    relationship_type_a_to_b: str = Field(..., description="Relationship from A to B")
    relationship_type_b_to_a: str = Field(..., description="Relationship from B to A")
    status: RelationshipStatus = Field(default=RelationshipStatus.PENDING, description="Relationship status")
    created_by: str = Field(..., description="User who initiated the relationship")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    activated_at: Optional[datetime] = Field(None, description="When relationship became active")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")

class FamilyInvitationDocument(BaseModel):
    """
    Database document model for family_invitations collection.
    """
    
    invitation_id: str = Field(..., description="Unique invitation identifier")
    family_id: str = Field(..., description="Target family")
    inviter_user_id: str = Field(..., description="User sending invitation")
    invitee_email: str = Field(..., description="Email of invited user")
    invitee_user_id: Optional[str] = Field(None, description="User ID if found in system")
    relationship_type: str = Field(..., description="Proposed relationship")
    invitation_token: str = Field(..., description="Secure token for email links")
    status: InvitationStatus = Field(default=InvitationStatus.PENDING, description="Invitation status")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    responded_at: Optional[datetime] = Field(None, description="Response timestamp")
    email_sent: bool = Field(default=False, description="Email delivery status")
    email_sent_at: Optional[datetime] = Field(None, description="Email sent timestamp")

class FamilyNotificationDocument(BaseModel):
    """
    Database document model for family_notifications collection.
    """
    
    notification_id: str = Field(..., description="Unique notification identifier")
    family_id: str = Field(..., description="Target family")
    recipient_user_ids: List[str] = Field(..., description="Users to notify")
    type: NotificationType = Field(..., description="Notification type")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification content")
    data: Dict[str, Any] = Field(default_factory=dict, description="Type-specific data")
    status: NotificationStatus = Field(default=NotificationStatus.PENDING, description="Notification status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    sent_at: Optional[datetime] = Field(None, description="Sent timestamp")
    read_by: Dict[str, datetime] = Field(default_factory=dict, description="Read status per user")

class FamilyTokenRequestDocument(BaseModel):
    """
    Database document model for family_token_requests collection.
    """
    
    request_id: str = Field(..., description="Unique request identifier")
    family_id: str = Field(..., description="Target family")
    requester_user_id: str = Field(..., description="User requesting tokens")
    amount: int = Field(..., description="Requested amount")
    reason: str = Field(..., description="Reason for request")
    status: TokenRequestStatus = Field(default=TokenRequestStatus.PENDING, description="Request status")
    reviewed_by: Optional[str] = Field(None, description="Admin who reviewed")
    admin_comments: Optional[str] = Field(None, description="Admin's comments")
    auto_approved: bool = Field(default=False, description="Whether auto-approved")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    reviewed_at: Optional[datetime] = Field(None, description="Review timestamp")
    processed_at: Optional[datetime] = Field(None, description="Processing timestamp")

# User collection updates for family support
class FamilyLimits(BaseModel):
    """Model for family limits in user documents."""
    
    max_families_allowed: int = Field(default=1, description="Maximum families user can join")
    max_members_per_family: int = Field(default=5, description="Maximum members per family for admin")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    updated_by: Optional[str] = Field(None, description="Who updated the limits")

class FamilyMembership(BaseModel):
    """Model for family membership in user documents."""
    
    family_id: str = Field(..., description="Family identifier")
    role: str = Field(..., description="Role in family: admin or member")
    joined_at: datetime = Field(default_factory=datetime.utcnow, description="Join timestamp")
    spending_permissions: Dict[str, Any] = Field(
        default_factory=lambda: {
            "can_spend": False,
            "spending_limit": 0,
            "last_updated": datetime.utcnow()
        },
        description="SBD spending permissions"
    )

class FamilyNotificationPreferences(BaseModel):
    """Model for family notification preferences in user documents."""
    
    unread_count: int = Field(default=0, description="Unread notification count")
    last_checked: Optional[datetime] = Field(None, description="Last check timestamp")
    preferences: Dict[str, bool] = Field(
        default_factory=lambda: {
            "email_notifications": True,
            "push_notifications": True,
            "sms_notifications": False
        },
        description="Notification delivery preferences"
    )