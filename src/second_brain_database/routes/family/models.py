"""Family management models for user relationships and shared resources."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

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
    "cousin": "cousin",
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
    TOKEN_TRANSFER_COMPLETED = "token_transfer_completed"
    DIRECT_TOKEN_TRANSFER_RECEIVED = "direct_token_transfer_received"
    DIRECT_TOKEN_TRANSFER_ADMIN = "direct_token_transfer_admin"
    RELATIONSHIP_MODIFIED = "relationship_modified"
    EMERGENCY_UNFREEZE_REQUEST = "emergency_unfreeze_request"
    EMERGENCY_UNFREEZE_EXECUTED = "emergency_unfreeze_executed"
    UPGRADE_SOON = "upgrade_soon"
    BILLING_RECOMMENDATION = "billing_recommendation"


# Status enums
class InvitationStatus(str, Enum):
    """Enumeration of invitation statuses."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


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
        json_schema_extra={"example": "Smith Family"},
    )

    model_config = {"json_schema_extra": {"example": {"name": "Smith Family"}}}


class InviteMemberRequest(BaseDocumentedModel):
    """
    Request model for inviting a family member.

    Requires the invitee's email and the relationship type from the inviter's perspective.
    """

    email: EmailStr = Field(
        ...,
        description="Email address of the user to invite to the family",
        json_schema_extra={"example": "john.doe@example.com"},
    )
    relationship_type: str = Field(
        ...,
        description="Relationship type from inviter's perspective (e.g., 'child', 'parent', 'sibling')",
        json_schema_extra={"example": "child"},
    )

    model_config = {"json_schema_extra": {"example": {"email": "john.doe@example.com", "relationship_type": "child"}}}

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
        json_schema_extra={"example": "accept"},
    )

    model_config = {"json_schema_extra": {"example": {"action": "accept"}}}

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
        ..., description="Relationship type from user A to user B", json_schema_extra={"example": "parent"}
    )
    relationship_type_b_to_a: str = Field(
        ..., description="Relationship type from user B to user A", json_schema_extra={"example": "child"}
    )

    model_config = {
        "json_schema_extra": {"example": {"relationship_type_a_to_b": "parent", "relationship_type_b_to_a": "child"}}
    }


class UpdateSpendingPermissionsRequest(BaseDocumentedModel):
    """
    Request model for updating family member spending permissions.
    """

    user_id: str = Field(
        ...,
        description="User ID of the family member to update permissions for",
        json_schema_extra={"example": "507f1f77bcf86cd799439011"},
    )
    spending_limit: int = Field(
        ...,
        description="Spending limit in SBD tokens. Use -1 for unlimited spending.",
        json_schema_extra={"example": 1000},
    )
    can_spend: bool = Field(
        ..., description="Whether the user can spend from the family account", json_schema_extra={"example": True}
    )

    model_config = {
        "json_schema_extra": {
            "example": {"user_id": "507f1f77bcf86cd799439011", "spending_limit": 1000, "can_spend": True}
        }
    }


class FreezeAccountRequest(BaseDocumentedModel):
    """
    Request model for freezing or unfreezing the family SBD account.
    """

    action: str = Field(
        ..., description="Action to take: 'freeze' or 'unfreeze'", json_schema_extra={"example": "freeze"}
    )
    reason: Optional[str] = Field(
        None,
        max_length=RELATIONSHIP_DESCRIPTION_MAX_LENGTH,
        description="Optional reason for the freeze action",
        json_schema_extra={"example": "Suspicious activity detected"},
    )

    model_config = {"json_schema_extra": {"example": {"action": "freeze", "reason": "Suspicious activity detected"}}}

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

    amount: int = Field(..., gt=0, description="Amount of SBD tokens to request", json_schema_extra={"example": 500})
    reason: str = Field(
        ...,
        max_length=TOKEN_REQUEST_REASON_MAX_LENGTH,
        description="Reason for the token request",
        json_schema_extra={"example": "Need tokens for school supplies"},
    )

    model_config = {"json_schema_extra": {"example": {"amount": 500, "reason": "Need tokens for school supplies"}}}


class ReviewTokenRequestRequest(BaseDocumentedModel):
    """
    Request model for reviewing a token request (admin only).
    """

    action: str = Field(
        ..., description="Action to take: 'approve' or 'deny'", json_schema_extra={"example": "approve"}
    )
    comments: Optional[str] = Field(
        None,
        max_length=TOKEN_REQUEST_REASON_MAX_LENGTH,
        description="Optional comments from the admin",
        json_schema_extra={"example": "Approved for educational expenses"},
    )

    model_config = {
        "json_schema_extra": {"example": {"action": "approve", "comments": "Approved for educational expenses"}}
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
        ..., description="Action to take: 'promote' or 'demote'", json_schema_extra={"example": "promote"}
    )

    model_config = {"json_schema_extra": {"example": {"action": "promote"}}}

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate that the action is either promote or demote."""
        if v.lower() not in ["promote", "demote"]:
            logger.error("Invalid admin action: %s", v)
            raise ValueError("Action must be either 'promote' or 'demote'")
        return v.lower()


class BackupAdminRequest(BaseDocumentedModel):
    """
    Request model for backup admin designation/removal.
    """

    action: str = Field(
        ..., description="Action to take: 'designate' or 'remove'", json_schema_extra={"example": "designate"}
    )

    model_config = {"json_schema_extra": {"example": {"action": "designate"}}}

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate that the action is either designate or remove."""
        if v.lower() not in ["designate", "remove"]:
            logger.error("Invalid backup admin action: %s", v)
            raise ValueError("Action must be either 'designate' or 'remove'")
        return v.lower()


class AdminActionsLogRequest(BaseDocumentedModel):
    """
    Request model for getting admin actions log.
    """

    limit: int = Field(
        50, ge=1, le=100, description="Maximum number of records to return", json_schema_extra={"example": 50}
    )
    offset: int = Field(0, ge=0, description="Number of records to skip", json_schema_extra={"example": 0})

    model_config = {"json_schema_extra": {"example": {"limit": 50, "offset": 0}}}


class InitiateRecoveryRequest(BaseDocumentedModel):
    """
    Request model for initiating account recovery.
    """

    recovery_reason: str = Field(
        ...,
        max_length=500,
        description="Reason for initiating account recovery",
        json_schema_extra={"example": "All admin accounts have been compromised"},
    )

    model_config = {"json_schema_extra": {"example": {"recovery_reason": "All admin accounts have been compromised"}}}


class VerifyRecoveryRequest(BaseDocumentedModel):
    """
    Request model for verifying account recovery.
    """

    verification_code: str = Field(
        ...,
        min_length=6,
        max_length=20,
        description="Verification code received via email or other method",
        json_schema_extra={"example": "ABC123"},
    )

    model_config = {"json_schema_extra": {"example": {"verification_code": "ABC123"}}}


# Response Models
class FamilyResponse(BaseDocumentedModel):
    """
    Response model for family information.

    Contains comprehensive family details including member count,
    SBD account information, and user's role in the family.
    """

    family_id: str = Field(
        ..., description="Unique family identifier", json_schema_extra={"example": "fam_1234567890abcdef"}
    )
    name: str = Field(..., description="Family name", json_schema_extra={"example": "Smith Family"})
    admin_user_ids: List[str] = Field(
        ...,
        description="List of user IDs who are family administrators",
        json_schema_extra={"example": ["507f1f77bcf86cd799439011"]},
    )
    member_count: int = Field(..., description="Total number of family members", json_schema_extra={"example": 4})
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the family was created",
        json_schema_extra={"example": "2024-01-01T12:00:00Z"},
    )
    is_admin: bool = Field(
        ..., description="Whether the current user is an admin of this family", json_schema_extra={"example": True}
    )
    sbd_account: Dict[str, Any] = Field(
        ...,
        description="Family SBD account information including balance and permissions",
        json_schema_extra={
            "example": {
                "account_username": "family_smith",
                "balance": 5000,
                "is_frozen": False,
                "spending_permissions": {},
            }
        },
    )
    usage_stats: Dict[str, Any] = Field(
        ...,
        description="Family usage statistics and limits",
        json_schema_extra={"example": {"current_members": 4, "max_members_allowed": 10, "can_add_members": True}},
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
                    "spending_permissions": {},
                },
                "usage_stats": {"current_members": 4, "max_members_allowed": 10, "can_add_members": True},
            }
        }
    }


class MemberPermissionsResponse(BaseDocumentedModel):
    """
    Response model for family member permissions.

    Contains spending permissions and limits for a family member.
    """

    can_spend: bool = Field(
        ..., description="Whether the member can spend from the family account", json_schema_extra={"example": True}
    )
    spending_limit: int = Field(
        ...,
        description="Spending limit in SBD tokens. Use -1 for unlimited spending.",
        json_schema_extra={"example": 1000},
    )
    last_updated: datetime = Field(
        ...,
        description="UTC timestamp when permissions were last updated",
        json_schema_extra={"example": "2024-01-01T12:00:00Z"},
    )
    updated_by: str = Field(
        ...,
        description="Username of the admin who last updated permissions",
        json_schema_extra={"example": "jane_smith"},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "can_spend": True,
                "spending_limit": 1000,
                "last_updated": "2024-01-01T12:00:00Z",
                "updated_by": "jane_smith",
            }
        }
    }


class InvitationResponse(BaseDocumentedModel):
    """
    Response model for family invitation information.
    """

    invitation_id: str = Field(
        ..., description="Unique invitation identifier", json_schema_extra={"example": "inv_1234567890abcdef"}
    )
    family_name: str = Field(
        ..., description="Name of the family the user is invited to", json_schema_extra={"example": "Smith Family"}
    )
    inviter_username: str = Field(
        ..., description="Username of the person who sent the invitation", json_schema_extra={"example": "jane_smith"}
    )
    invitee_email: Optional[str] = Field(
        None,
        description="Email of the invited user (if available)",
        json_schema_extra={"example": "john.doe@example.com"},
    )
    invitee_username: Optional[str] = Field(
        None, description="Username of the invited user (if available)", json_schema_extra={"example": "john_doe"}
    )
    relationship_type: str = Field(
        ..., description="Proposed relationship type", json_schema_extra={"example": "child"}
    )
    status: InvitationStatus = Field(
        ..., description="Current status of the invitation", json_schema_extra={"example": InvitationStatus.PENDING}
    )
    expires_at: datetime = Field(
        ...,
        description="UTC timestamp when the invitation expires",
        json_schema_extra={"example": "2024-01-08T12:00:00Z"},
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the invitation was created",
        json_schema_extra={"example": "2024-01-01T12:00:00Z"},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "invitation_id": "inv_1234567890abcdef",
                "family_name": "Smith Family",
                "inviter_username": "jane_smith",
                "invitee_email": "john.doe@example.com",
                "invitee_username": "john_doe",
                "relationship_type": "child",
                "status": "pending",
                "expires_at": "2024-01-08T12:00:00Z",
                "created_at": "2024-01-01T12:00:00Z",
            }
        }
    }


class ReceivedInvitationResponse(BaseDocumentedModel):
    """
    Response model for invitations received by a user.

    Used by GET /family/my-invitations endpoint to show invitations
    sent TO the current authenticated user.
    """

    invitation_id: str = Field(
        ..., description="Unique invitation identifier", json_schema_extra={"example": "inv_abc123xyz789"}
    )
    family_id: str = Field(
        ...,
        description="ID of the family the user is invited to join",
        json_schema_extra={"example": "fam_def456uvw012"},
    )
    family_name: str = Field(..., description="Name of the family", json_schema_extra={"example": "Johnson Family"})
    inviter_user_id: str = Field(
        ..., description="User ID of the person who sent the invitation", json_schema_extra={"example": "user_123abc"}
    )
    inviter_username: str = Field(
        ..., description="Username of the inviter", json_schema_extra={"example": "john_johnson"}
    )
    relationship_type: str = Field(
        ..., description="Proposed relationship type for the invitee", json_schema_extra={"example": "child"}
    )
    status: InvitationStatus = Field(
        ..., description="Current invitation status", json_schema_extra={"example": InvitationStatus.PENDING}
    )
    expires_at: datetime = Field(
        ..., description="UTC timestamp when invitation expires", json_schema_extra={"example": "2025-10-28T14:30:00Z"}
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when invitation was created",
        json_schema_extra={"example": "2025-10-21T14:30:00Z"},
    )
    invitation_token: Optional[str] = Field(
        None,
        description="Optional token for email-based invitation acceptance",
        json_schema_extra={"example": "tok_xyz789abc123"},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "invitation_id": "inv_abc123xyz789",
                "family_id": "fam_def456uvw012",
                "family_name": "Johnson Family",
                "inviter_user_id": "user_123abc",
                "inviter_username": "john_johnson",
                "relationship_type": "child",
                "status": "pending",
                "expires_at": "2025-10-28T14:30:00Z",
                "created_at": "2025-10-21T14:30:00Z",
                "invitation_token": "tok_xyz789abc123",
            }
        }
    }


class SBDAccountResponse(BaseDocumentedModel):
    """
    Response model for family SBD account information.
    """

    account_username: str = Field(
        ..., description="Virtual account username for the family", json_schema_extra={"example": "family_smith"}
    )
    balance: int = Field(..., description="Current SBD token balance", json_schema_extra={"example": 5000})
    is_frozen: bool = Field(
        ..., description="Whether the account is currently frozen", json_schema_extra={"example": False}
    )
    frozen_by: Optional[str] = Field(
        None, description="Username of admin who froze the account", json_schema_extra={"example": None}
    )
    member_permissions: Dict[str, Any] = Field(
        ...,
        description="Spending permissions for all family members",
        json_schema_extra={
            "example": {
                "507f1f77bcf86cd799439011": {
                    "can_spend": True,
                    "spending_limit": 1000,
                    "updated_by": "jane_smith",
                    "updated_at": "2024-01-01T12:00:00Z",
                }
            }
        },
    )
    recent_transactions: List[Dict[str, Any]] = Field(
        ...,
        description="Recent SBD token transactions",
        json_schema_extra={
            "example": [
                {
                    "type": "spend",
                    "amount": 100,
                    "from_user": "john_doe",
                    "to_user": "shop_system",
                    "timestamp": "2024-01-01T15:00:00Z",
                    "transaction_id": "txn_1234567890",
                }
            ]
        },
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "account_username": "family_smith",
                "balance": 5000,
                "is_frozen": False,
                "frozen_by": None,
                "member_permissions": {
                    "507f1f77bcf86cd799439011": {
                        "can_spend": True,
                        "spending_limit": 1000,
                        "updated_by": "jane_smith",
                        "updated_at": "2024-01-01T12:00:00Z",
                    }
                },
                "recent_transactions": [
                    {
                        "type": "spend",
                        "amount": 100,
                        "from_user": "john_doe",
                        "to_user": "shop_system",
                        "timestamp": "2024-01-01T15:00:00Z",
                        "transaction_id": "txn_1234567890",
                    }
                ],
            }
        }
    }


class TokenRequestResponse(BaseDocumentedModel):
    """
    Response model for token request information.
    """

    request_id: str = Field(
        ..., description="Unique token request identifier", json_schema_extra={"example": "req_1234567890abcdef"}
    )
    requester_username: str = Field(
        ..., description="Username of the person who made the request", json_schema_extra={"example": "john_doe"}
    )
    from_user_id: Optional[str] = Field(
        None,
        description="Canonical 'from' user id (same as requester_user_id for token requests)",
        json_schema_extra={"example": "68f3c68604839468a2f226f0"},
    )
    from_username: Optional[str] = Field(
        None,
        description="Canonical 'from' username (same as requester_username for token requests)",
        json_schema_extra={"example": "john_doe"},
    )
    amount: int = Field(..., description="Amount of SBD tokens requested", json_schema_extra={"example": 500})
    reason: str = Field(
        ...,
        description="Reason provided for the token request",
        json_schema_extra={"example": "Need tokens for school supplies"},
    )
    status: TokenRequestStatus = Field(
        ..., description="Current status of the request", json_schema_extra={"example": TokenRequestStatus.PENDING}
    )
    auto_approved: bool = Field(
        ..., description="Whether the request was automatically approved", json_schema_extra={"example": False}
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the request was created",
        json_schema_extra={"example": "2024-01-01T12:00:00Z"},
    )
    expires_at: datetime = Field(
        ..., description="UTC timestamp when the request expires", json_schema_extra={"example": "2024-01-08T12:00:00Z"}
    )
    admin_comments: Optional[str] = Field(
        None,
        description="Comments from the admin who reviewed the request",
        json_schema_extra={"example": "Approved for educational expenses"},
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
                "admin_comments": None,
            }
        }
    }


class NotificationResponse(BaseDocumentedModel):
    """
    Response model for family notification information.
    """

    notification_id: str = Field(
        ..., description="Unique notification identifier", json_schema_extra={"example": "not_1234567890abcdef"}
    )
    type: NotificationType = Field(
        ..., description="Type of notification", json_schema_extra={"example": NotificationType.SBD_SPEND}
    )
    title: str = Field(..., description="Notification title", json_schema_extra={"example": "SBD Token Spending"})
    message: str = Field(
        ...,
        description="Notification message content",
        json_schema_extra={"example": "John spent 100 SBD tokens at the shop"},
    )
    data: Dict[str, Any] = Field(
        ...,
        description="Additional notification data",
        json_schema_extra={
            "example": {
                "transaction_id": "txn_1234567890",
                "amount": 100,
                "from_user": "john_doe",
                "to_user": "shop_system",
            }
        },
    )
    status: NotificationStatus = Field(
        ..., description="Current notification status", json_schema_extra={"example": NotificationStatus.SENT}
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the notification was created",
        json_schema_extra={"example": "2024-01-01T15:00:00Z"},
    )
    is_read: bool = Field(
        ..., description="Whether the current user has read this notification", json_schema_extra={"example": False}
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
                    "to_user": "shop_system",
                },
                "status": "sent",
                "created_at": "2024-01-01T15:00:00Z",
                "is_read": False,
            }
        }
    }


class AdminActionResponse(BaseDocumentedModel):
    """
    Response model for admin promotion/demotion actions.
    """

    family_id: str = Field(..., description="Family identifier", json_schema_extra={"example": "fam_1234567890abcdef"})
    target_user_id: str = Field(
        ..., description="User ID of the target user", json_schema_extra={"example": "507f1f77bcf86cd799439011"}
    )
    target_username: str = Field(
        ..., description="Username of the target user", json_schema_extra={"example": "john_doe"}
    )
    action: str = Field(
        ..., description="Action performed: 'promoted' or 'demoted'", json_schema_extra={"example": "promoted"}
    )
    new_role: str = Field(
        ..., description="New role of the user: 'admin' or 'member'", json_schema_extra={"example": "admin"}
    )
    performed_by: str = Field(
        ...,
        description="User ID of the admin who performed the action",
        json_schema_extra={"example": "507f1f77bcf86cd799439012"},
    )
    performed_by_username: str = Field(
        ..., description="Username of the admin who performed the action", json_schema_extra={"example": "jane_smith"}
    )
    performed_at: datetime = Field(
        ...,
        description="UTC timestamp when the action was performed",
        json_schema_extra={"example": "2024-01-01T12:00:00Z"},
    )
    message: str = Field(
        ...,
        description="Success message",
        json_schema_extra={"example": "User successfully promoted to family administrator"},
    )
    transaction_safe: bool = Field(
        True,
        description="Whether the operation was performed with transaction safety",
        json_schema_extra={"example": True},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "family_id": "fam_1234567890abcdef",
                "target_user_id": "507f1f77bcf86cd799439011",
                "target_username": "john_doe",
                "action": "promoted",
                "new_role": "admin",
                "performed_by": "507f1f77bcf86cd799439012",
                "performed_by_username": "jane_smith",
                "performed_at": "2024-01-01T12:00:00Z",
                "message": "User successfully promoted to family administrator",
                "transaction_safe": True,
            }
        }
    }


class BackupAdminResponse(BaseDocumentedModel):
    """
    Response model for backup admin designation/removal.
    """

    family_id: str = Field(..., description="Family identifier", json_schema_extra={"example": "fam_1234567890abcdef"})
    backup_user_id: str = Field(
        ..., description="User ID of the backup admin", json_schema_extra={"example": "507f1f77bcf86cd799439011"}
    )
    backup_username: str = Field(
        ..., description="Username of the backup admin", json_schema_extra={"example": "john_doe"}
    )
    action: str = Field(
        ..., description="Action performed: 'designated' or 'removed'", json_schema_extra={"example": "designated"}
    )
    role: str = Field(
        ..., description="Role designation: 'backup_admin'", json_schema_extra={"example": "backup_admin"}
    )
    performed_by: str = Field(
        ...,
        description="User ID of the admin who performed the action",
        json_schema_extra={"example": "507f1f77bcf86cd799439012"},
    )
    performed_by_username: str = Field(
        ..., description="Username of the admin who performed the action", json_schema_extra={"example": "jane_smith"}
    )
    performed_at: datetime = Field(
        ...,
        description="UTC timestamp when the action was performed",
        json_schema_extra={"example": "2024-01-01T12:00:00Z"},
    )
    message: str = Field(
        ...,
        description="Success message",
        json_schema_extra={"example": "User successfully designated as backup administrator"},
    )
    transaction_safe: bool = Field(
        True,
        description="Whether the operation was performed with transaction safety",
        json_schema_extra={"example": True},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "family_id": "fam_1234567890abcdef",
                "backup_user_id": "507f1f77bcf86cd799439011",
                "backup_username": "john_doe",
                "action": "designated",
                "role": "backup_admin",
                "performed_by": "507f1f77bcf86cd799439012",
                "performed_by_username": "jane_smith",
                "performed_at": "2024-01-01T12:00:00Z",
                "message": "User successfully designated as backup administrator",
                "transaction_safe": True,
            }
        }
    }


class AdminActionLogEntry(BaseDocumentedModel):
    """
    Model for individual admin action log entry.
    """

    action_id: str = Field(
        ..., description="Unique action identifier", json_schema_extra={"example": "act_1234567890abcdef"}
    )
    family_id: str = Field(..., description="Family identifier", json_schema_extra={"example": "fam_1234567890abcdef"})
    admin_user_id: str = Field(
        ...,
        description="User ID of the admin who performed the action",
        json_schema_extra={"example": "507f1f77bcf86cd799439012"},
    )
    admin_username: str = Field(
        ..., description="Username of the admin who performed the action", json_schema_extra={"example": "jane_smith"}
    )
    target_user_id: str = Field(
        ..., description="User ID of the target user", json_schema_extra={"example": "507f1f77bcf86cd799439011"}
    )
    target_username: str = Field(
        ..., description="Username of the target user", json_schema_extra={"example": "john_doe"}
    )
    action_type: str = Field(
        ..., description="Type of action performed", json_schema_extra={"example": "promote_to_admin"}
    )
    details: Dict[str, Any] = Field(
        ...,
        description="Additional action details",
        json_schema_extra={"example": {"previous_role": "member", "new_role": "admin"}},
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the action was performed",
        json_schema_extra={"example": "2024-01-01T12:00:00Z"},
    )
    ip_address: Optional[str] = Field(
        None,
        description="IP address from which the action was performed",
        json_schema_extra={"example": "192.168.1.100"},
    )
    user_agent: Optional[str] = Field(
        None,
        description="User agent string from the request",
        json_schema_extra={"example": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "action_id": "act_1234567890abcdef",
                "family_id": "fam_1234567890abcdef",
                "admin_user_id": "507f1f77bcf86cd799439012",
                "admin_username": "jane_smith",
                "target_user_id": "507f1f77bcf86cd799439011",
                "target_username": "john_doe",
                "action_type": "promote_to_admin",
                "details": {"previous_role": "member", "new_role": "admin"},
                "created_at": "2024-01-01T12:00:00Z",
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
        }
    }


class AdminActionsLogResponse(BaseDocumentedModel):
    """
    Response model for admin actions log.
    """

    family_id: str = Field(..., description="Family identifier", json_schema_extra={"example": "fam_1234567890abcdef"})
    actions: List[AdminActionLogEntry] = Field(
        ..., description="List of admin actions", json_schema_extra={"example": []}
    )
    pagination: Dict[str, Any] = Field(
        ...,
        description="Pagination information",
        json_schema_extra={"example": {"total_count": 25, "limit": 50, "offset": 0, "has_more": False}},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "family_id": "fam_1234567890abcdef",
                "actions": [
                    {
                        "action_id": "act_1234567890abcdef",
                        "family_id": "fam_1234567890abcdef",
                        "admin_user_id": "507f1f77bcf86cd799439012",
                        "admin_username": "jane_smith",
                        "target_user_id": "507f1f77bcf86cd799439011",
                        "target_username": "john_doe",
                        "action_type": "promote_to_admin",
                        "details": {"previous_role": "member", "new_role": "admin"},
                        "created_at": "2024-01-01T12:00:00Z",
                        "ip_address": "192.168.1.100",
                        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    }
                ],
                "pagination": {"total_count": 25, "limit": 50, "offset": 0, "has_more": False},
            }
        }
    }


class FamilyUsageStats(BaseModel):
    """Model for detailed family usage statistics."""

    family_id: str = Field(..., description="Family identifier")
    name: str = Field(..., description="Family name")
    member_count: int = Field(..., description="Current member count")
    max_members_allowed: int = Field(..., description="Maximum members allowed for this family")
    is_admin: bool = Field(..., description="Whether user is admin of this family")
    can_add_members: bool = Field(..., description="Whether user can add more members")
    members_remaining: int = Field(..., description="Number of members that can still be added")
    created_at: datetime = Field(..., description="When family was created")
    last_activity: Optional[datetime] = Field(None, description="Last family activity timestamp")


class FamilyLimitStatus(BaseModel):
    """Model for family limit status and enforcement."""

    limit_type: str = Field(..., description="Type of limit (families, members)")
    current_usage: int = Field(..., description="Current usage count")
    max_allowed: int = Field(..., description="Maximum allowed count")
    percentage_used: float = Field(..., description="Percentage of limit used")
    is_at_limit: bool = Field(..., description="Whether at the limit")
    is_over_limit: bool = Field(..., description="Whether over the limit")
    grace_period_expires: Optional[datetime] = Field(None, description="When grace period expires")
    upgrade_required: bool = Field(..., description="Whether upgrade is required")


class BillingUsageMetrics(BaseModel):
    """Model for billing-related usage metrics."""

    period_start: datetime = Field(..., description="Start of tracking period")
    period_end: datetime = Field(..., description="End of tracking period")
    peak_families: int = Field(..., description="Peak number of families in period")
    peak_members_total: int = Field(..., description="Peak total members across all families")
    average_families: float = Field(..., description="Average families in period")
    average_members_total: float = Field(..., description="Average total members in period")
    family_creation_events: int = Field(..., description="Number of families created in period")
    member_addition_events: int = Field(..., description="Number of members added in period")
    upgrade_recommendations: List[str] = Field(default_factory=list, description="Upgrade recommendations")


class FamilyLimitsResponse(BaseDocumentedModel):
    """
    Enhanced response model for family limits and usage information with billing integration.
    """

    max_families_allowed: int = Field(
        ..., description="Maximum number of families the user can create or join", json_schema_extra={"example": 1}
    )
    max_members_per_family: int = Field(
        ...,
        description="Maximum number of members per family for families where user is admin",
        json_schema_extra={"example": 5},
    )
    current_families: int = Field(
        ..., description="Current number of families the user belongs to", json_schema_extra={"example": 1}
    )
    families_usage: List[FamilyUsageStats] = Field(
        ...,
        description="Detailed usage statistics for each family",
        json_schema_extra={
            "example": [
                {
                    "family_id": "fam_1234567890abcdef",
                    "name": "Smith Family",
                    "member_count": 4,
                    "max_members_allowed": 5,
                    "is_admin": True,
                    "can_add_members": True,
                    "members_remaining": 1,
                    "created_at": "2024-01-01T00:00:00Z",
                    "last_activity": "2024-01-15T12:00:00Z",
                }
            ]
        },
    )
    can_create_family: bool = Field(
        ..., description="Whether the user can create a new family", json_schema_extra={"example": False}
    )
    upgrade_required: bool = Field(
        ..., description="Whether an upgrade is required to increase limits", json_schema_extra={"example": True}
    )
    limit_status: List[FamilyLimitStatus] = Field(
        ...,
        description="Detailed status for each type of limit",
        json_schema_extra={
            "example": [
                {
                    "limit_type": "families",
                    "current_usage": 1,
                    "max_allowed": 1,
                    "percentage_used": 100.0,
                    "is_at_limit": True,
                    "is_over_limit": False,
                    "grace_period_expires": None,
                    "upgrade_required": True,
                }
            ]
        },
    )
    billing_metrics: Optional[BillingUsageMetrics] = Field(
        None, description="Billing-related usage metrics for the current period"
    )
    upgrade_messaging: Dict[str, Any] = Field(
        ...,
        description="Messaging and recommendations for upgrades",
        json_schema_extra={
            "example": {
                "primary_message": "You've reached your family limit",
                "upgrade_benefits": ["Create unlimited families", "Add up to 20 members per family"],
                "call_to_action": "Upgrade to Pro to unlock more families",
                "upgrade_url": "/billing/upgrade",
            }
        },
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
                        "max_members_allowed": 5,
                        "is_admin": True,
                        "can_add_members": True,
                        "members_remaining": 1,
                        "created_at": "2024-01-01T00:00:00Z",
                        "last_activity": "2024-01-15T12:00:00Z",
                    }
                ],
                "can_create_family": False,
                "upgrade_required": True,
                "limit_status": [
                    {
                        "limit_type": "families",
                        "current_usage": 1,
                        "max_allowed": 1,
                        "percentage_used": 100.0,
                        "is_at_limit": True,
                        "is_over_limit": False,
                        "grace_period_expires": None,
                        "upgrade_required": True,
                    }
                ],
                "billing_metrics": {
                    "period_start": "2024-01-01T00:00:00Z",
                    "period_end": "2024-01-31T23:59:59Z",
                    "peak_families": 1,
                    "peak_members_total": 4,
                    "average_families": 1.0,
                    "average_members_total": 4.0,
                    "family_creation_events": 1,
                    "member_addition_events": 3,
                    "upgrade_recommendations": ["Consider Pro plan for unlimited families"],
                },
                "upgrade_messaging": {
                    "primary_message": "You've reached your family limit",
                    "upgrade_benefits": ["Create unlimited families", "Add up to 20 members per family"],
                    "call_to_action": "Upgrade to Pro to unlock more families",
                    "upgrade_url": "/billing/upgrade",
                },
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
                "notify_admins_only": False,
            },
        },
        description="SBD account configuration",
    )

    # Family settings
    settings: Dict[str, Any] = Field(
        default_factory=lambda: {
            "allow_member_invites": False,
            "visibility": "private",
            "auto_approval_threshold": 100,
            "request_expiry_hours": 168,  # 7 days
        },
        description="Family configuration settings",
    )

    # Succession planning
    succession_plan: Dict[str, Any] = Field(
        default_factory=lambda: {"backup_admins": [], "recovery_contacts": []},
        description="Admin succession and recovery configuration",
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
    joined_at: datetime = Field(default_factory=datetime.now(timezone.utc), description="Join timestamp")
    spending_permissions: Dict[str, Any] = Field(
        default_factory=lambda: {"can_spend": False, "spending_limit": 0, "last_updated": datetime.now(timezone.utc)},
        description="SBD spending permissions",
    )


class FamilyNotificationPreferences(BaseModel):
    """Model for family notification preferences in user documents."""

    unread_count: int = Field(default=0, description="Unread notification count")
    last_checked: Optional[datetime] = Field(None, description="Last check timestamp")
    preferences: Dict[str, bool] = Field(
        default_factory=lambda: {"email_notifications": True, "push_notifications": True, "sms_notifications": False},
        description="Notification delivery preferences",
    )


# Notification request models
class MarkNotificationsReadRequest(BaseModel):
    """Request model for marking notifications as read."""

    notification_ids: List[str] = Field(
        ...,
        description="List of notification IDs to mark as read",
        json_schema_extra={
            "example": ["notif_1234567890abcdef", "notif_fedcba0987654321"],
        },
    )


class UpdateNotificationPreferencesRequest(BaseModel):
    """Request model for updating notification preferences."""

    preferences: Dict[str, bool] = Field(
        ...,
        description="Notification preference settings",
        json_schema_extra={
            "example": {"email_notifications": True, "push_notifications": False, "sms_notifications": False}
        },
    )


class NotificationListResponse(BaseDocumentedModel):
    """Response model for notification list with pagination."""

    notifications: List[NotificationResponse] = Field(..., description="List of notifications")
    total_count: int = Field(..., description="Total number of notifications", json_schema_extra={"example": 25})
    unread_count: int = Field(..., description="Number of unread notifications", json_schema_extra={"example": 5})
    has_more: bool = Field(
        ..., description="Whether there are more notifications available", json_schema_extra={"example": True}
    )
    pagination: Dict[str, Any] = Field(
        ...,
        description="Pagination information",
        json_schema_extra={"example": {"limit": 20, "offset": 0, "next_offset": 20}},
    )


class NotificationPreferencesResponse(BaseDocumentedModel):
    """Response model for notification preferences."""

    preferences: Dict[str, bool] = Field(
        ...,
        description="Current notification preferences",
        json_schema_extra={
            "example": {"email_notifications": True, "push_notifications": True, "sms_notifications": False}
        },
    )
    unread_count: int = Field(..., description="Current unread notification count", json_schema_extra={"example": 3})
    last_checked: Optional[datetime] = Field(
        None, description="Last time notifications were checked", json_schema_extra={"example": "2024-01-01T15:00:00Z"}
    )


# Additional request models for new endpoints


class InviteMemberRequest(BaseDocumentedModel):
    """
    Enhanced request model for inviting a family member.

    Supports both email and username identification with proper validation.
    """

    identifier: str = Field(
        ...,
        description="Email address or username of the user to invite",
        json_schema_extra={"example": "john.doe@example.com"},
    )
    relationship_type: str = Field(
        ..., description="Relationship type from inviter's perspective", json_schema_extra={"example": "child"}
    )
    identifier_type: str = Field(
        "email", description="Type of identifier: 'email' or 'username'", json_schema_extra={"example": "email"}
    )

    model_config = {
        "json_schema_extra": {
            "example": {"identifier": "john.doe@example.com", "relationship_type": "child", "identifier_type": "email"}
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

    @field_validator("identifier_type")
    @classmethod
    def validate_identifier_type(cls, v: str) -> str:
        """Validate that the identifier type is supported."""
        if v.lower() not in ["email", "username"]:
            logger.error("Invalid identifier type: %s", v)
            raise ValueError("Identifier type must be either 'email' or 'username'")
        return v.lower()


class MarkNotificationsReadRequest(BaseDocumentedModel):
    """
    Request model for marking notifications as read.
    """

    notification_ids: List[str] = Field(
        ...,
        description="List of notification IDs to mark as read",
        json_schema_extra={
            "example": ["not_1234567890abcdef", "not_abcdef1234567890"],
        },
    )

    model_config = {
        "json_schema_extra": {"example": {"notification_ids": ["not_1234567890abcdef", "not_abcdef1234567890"]}}
    }


class UpdateNotificationPreferencesRequest(BaseDocumentedModel):
    """
    Request model for updating notification preferences.
    """

    email_notifications: Optional[bool] = Field(
        None, description="Enable/disable email notifications", json_schema_extra={"example": True}
    )
    push_notifications: Optional[bool] = Field(
        None, description="Enable/disable push notifications", json_schema_extra={"example": True}
    )
    sms_notifications: Optional[bool] = Field(
        None, description="Enable/disable SMS notifications", json_schema_extra={"example": False}
    )

    model_config = {
        "json_schema_extra": {
            "example": {"email_notifications": True, "push_notifications": True, "sms_notifications": False}
        }
    }


# Additional response models


class NotificationListResponse(BaseDocumentedModel):
    """
    Response model for paginated notification list.
    """

    notifications: List[NotificationResponse] = Field(
        ..., description="List of notifications", json_schema_extra={"example": []}
    )
    pagination: Dict[str, Any] = Field(
        ...,
        description="Pagination information",
        json_schema_extra={"example": {"limit": 50, "offset": 0, "total_count": 150, "has_more": True}},
    )
    unread_count: int = Field(..., description="Total unread notification count", json_schema_extra={"example": 5})

    model_config = {
        "json_schema_extra": {
            "example": {
                "notifications": [],
                "pagination": {"limit": 50, "offset": 0, "total_count": 150, "has_more": True},
                "unread_count": 5,
            }
        }
    }


class FamilyLimitsResponse(BaseDocumentedModel):
    """
    Response model for family limits and usage information.
    """

    max_families_allowed: int = Field(
        ..., description="Maximum number of families user can create/join", json_schema_extra={"example": 3}
    )
    max_members_per_family: int = Field(
        ..., description="Maximum members per family for user's families", json_schema_extra={"example": 10}
    )
    current_families: int = Field(
        ..., description="Current number of families user belongs to", json_schema_extra={"example": 2}
    )
    families_usage: List[Dict[str, Any]] = Field(
        ...,
        description="Usage details for each family",
        json_schema_extra={
            "example": [
                {"family_id": "fam_1234567890abcdef", "name": "Smith Family", "member_count": 4, "is_admin": True}
            ]
        },
    )
    can_create_family: bool = Field(
        ..., description="Whether user can create another family", json_schema_extra={"example": True}
    )
    upgrade_required: bool = Field(
        ..., description="Whether upgrade is needed for more families", json_schema_extra={"example": False}
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "max_families_allowed": 3,
                "max_members_per_family": 10,
                "current_families": 2,
                "families_usage": [
                    {"family_id": "fam_1234567890abcdef", "name": "Smith Family", "member_count": 4, "is_admin": True}
                ],
                "can_create_family": True,
                "upgrade_required": False,
            }
        }
    }


class RecoveryInitiationResponse(BaseDocumentedModel):
    """
    Response model for account recovery initiation.
    """

    recovery_id: str = Field(
        ..., description="Unique recovery request identifier", json_schema_extra={"example": "rec_1234567890abcdef"}
    )
    family_id: str = Field(..., description="Family identifier", json_schema_extra={"example": "fam_1234567890abcdef"})
    status: str = Field(..., description="Recovery status", json_schema_extra={"example": "pending_verification"})
    required_verifications: int = Field(
        ..., description="Number of verifications required to complete recovery", json_schema_extra={"example": 2}
    )
    expires_at: datetime = Field(
        ...,
        description="UTC timestamp when the recovery request expires",
        json_schema_extra={"example": "2024-01-04T12:00:00Z"},
    )
    message: str = Field(
        ...,
        description="Status message",
        json_schema_extra={"example": "Account recovery initiated. Multi-member verification required."},
    )
    transaction_safe: bool = Field(
        True,
        description="Whether the operation was performed with transaction safety",
        json_schema_extra={"example": True},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "recovery_id": "rec_1234567890abcdef",
                "family_id": "fam_1234567890abcdef",
                "status": "pending_verification",
                "required_verifications": 2,
                "expires_at": "2024-01-04T12:00:00Z",
                "message": "Account recovery initiated. Multi-member verification required.",
                "transaction_safe": True,
            }
        }
    }


class RecoveryVerificationResponse(BaseDocumentedModel):
    """
    Response model for account recovery verification.
    """

    recovery_id: str = Field(
        ..., description="Recovery request identifier", json_schema_extra={"example": "rec_1234567890abcdef"}
    )
    verification_accepted: bool = Field(
        ..., description="Whether the verification was accepted", json_schema_extra={"example": True}
    )
    current_verifications: int = Field(
        ..., description="Current number of verifications received", json_schema_extra={"example": 1}
    )
    required_verifications: int = Field(
        ..., description="Total number of verifications required", json_schema_extra={"example": 2}
    )
    recovery_complete: bool = Field(
        ..., description="Whether the recovery process is complete", json_schema_extra={"example": False}
    )
    promoted_user_id: Optional[str] = Field(
        None,
        description="User ID of promoted admin (if recovery complete)",
        json_schema_extra={"example": "507f1f77bcf86cd799439011"},
    )
    promoted_username: Optional[str] = Field(
        None, description="Username of promoted admin (if recovery complete)", json_schema_extra={"example": "john_doe"}
    )
    message: str = Field(
        ...,
        description="Status message",
        json_schema_extra={"example": "Verification accepted. 1 more verification needed."},
    )
    transaction_safe: bool = Field(
        True,
        description="Whether the operation was performed with transaction safety",
        json_schema_extra={"example": True},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "recovery_id": "rec_1234567890abcdef",
                "verification_accepted": True,
                "current_verifications": 1,
                "required_verifications": 2,
                "recovery_complete": False,
                "promoted_user_id": None,
                "promoted_username": None,
                "message": "Verification accepted. 1 more verification needed.",
                "transaction_safe": True,
            }
        }
    }


# Request Models for Relationship Management
class ModifyRelationshipRequest(BaseDocumentedModel):
    """
    Request model for modifying family relationship types.

    This model validates the request to change the relationship type between
    two family members. Only family administrators can modify relationships.
    """

    user_a_id: str = Field(..., description="ID of the first user in the relationship", min_length=1, max_length=100)

    user_b_id: str = Field(..., description="ID of the second user in the relationship", min_length=1, max_length=100)

    new_relationship_type: str = Field(
        ..., description="New relationship type from user_a's perspective", min_length=1, max_length=50
    )

    @field_validator("new_relationship_type")
    @classmethod
    def validate_relationship_type(cls, v: str) -> str:
        """Validate that the relationship type is supported."""
        if v not in RELATIONSHIP_TYPES:
            raise ValueError(f"Invalid relationship type. Must be one of: {list(RELATIONSHIP_TYPES.keys())}")
        return v

    @field_validator("user_a_id", "user_b_id")
    @classmethod
    def validate_user_ids_different(cls, v: str, info) -> str:
        """Validate that user IDs are different."""
        if hasattr(info, "data") and info.data:
            if v == info.data.get("user_a_id") or v == info.data.get("user_b_id"):
                if info.field_name == "user_b_id" and v == info.data.get("user_a_id"):
                    raise ValueError("User IDs must be different")
        return v

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "user_a_id": "user_1234567890abcdef",
                "user_b_id": "user_fedcba0987654321",
                "new_relationship_type": "sibling",
            }
        }


# Response Models for Relationship Management
class ModifyRelationshipResponse(BaseDocumentedModel):
    """
    Response model for relationship modification results.

    This model provides comprehensive information about the relationship
    modification including the old and new relationship types.
    """

    relationship_id: str = Field(..., description="Unique identifier for the relationship")

    family_id: str = Field(..., description="ID of the family containing the relationship")

    user_a_id: str = Field(..., description="ID of the first user in the relationship")

    user_b_id: str = Field(..., description="ID of the second user in the relationship")

    old_relationship_type: str = Field(..., description="Previous relationship type from user_a's perspective")

    new_relationship_type: str = Field(..., description="New relationship type from user_a's perspective")

    new_reciprocal_type: str = Field(..., description="New reciprocal relationship type from user_b's perspective")

    modified_by: str = Field(..., description="ID of the admin who modified the relationship")

    modified_at: datetime = Field(..., description="Timestamp when the relationship was modified")

    transaction_safe: bool = Field(..., description="Whether the operation was completed with transaction safety")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "relationship_id": "rel_1234567890abcdef",
                "family_id": "fam_1234567890abcdef",
                "user_a_id": "user_1234567890abcdef",
                "user_b_id": "user_fedcba0987654321",
                "old_relationship_type": "cousin",
                "new_relationship_type": "sibling",
                "new_reciprocal_type": "sibling",
                "modified_by": "user_admin123456789",
                "modified_at": "2024-01-15T10:30:00Z",
                "transaction_safe": True,
            }
        }


class RelationshipDetailsResponse(BaseDocumentedModel):
    """
    Response model for detailed relationship information.

    This model provides comprehensive information about a family relationship
    including both users' perspectives and metadata.
    """

    relationship_id: str = Field(..., description="Unique identifier for the relationship")

    family_id: str = Field(..., description="ID of the family containing the relationship")

    user_a: Dict[str, Any] = Field(
        ..., description="Information about the first user including username and relationship type"
    )

    user_b: Dict[str, Any] = Field(
        ..., description="Information about the second user including username and relationship type"
    )

    status: str = Field(..., description="Status of the relationship (active, pending, etc.)")

    created_by: str = Field(..., description="ID of the user who created the relationship")

    created_at: datetime = Field(..., description="Timestamp when the relationship was created")

    updated_at: datetime = Field(..., description="Timestamp when the relationship was last updated")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "relationship_id": "rel_1234567890abcdef",
                "family_id": "fam_1234567890abcdef",
                "user_a": {"user_id": "user_1234567890abcdef", "username": "john_doe", "relationship_type": "parent"},
                "user_b": {"user_id": "user_fedcba0987654321", "username": "jane_doe", "relationship_type": "child"},
                "status": "active",
                "created_by": "user_1234567890abcdef",
                "created_at": "2024-01-10T08:00:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
            }
        }


# Enhanced models for family limits and billing integration


class UpdateFamilyLimitsRequest(BaseDocumentedModel):
    """
    Request model for updating user family limits (admin/billing system use).
    """

    max_families_allowed: Optional[int] = Field(
        None, ge=0, description="Maximum number of families the user can create or join"
    )
    max_members_per_family: Optional[int] = Field(
        None, ge=1, description="Maximum number of members per family for families where user is admin"
    )
    reason: Optional[str] = Field(None, description="Reason for the limit change (for audit purposes)")
    effective_date: Optional[datetime] = Field(
        None, description="When the new limits should take effect (defaults to now)"
    )
    grace_period_days: Optional[int] = Field(None, ge=0, description="Grace period in days for limit downgrades")

    model_config = {
        "json_schema_extra": {
            "example": {
                "max_families_allowed": 3,
                "max_members_per_family": 10,
                "reason": "User upgraded to Pro plan",
                "effective_date": "2024-01-01T00:00:00Z",
                "grace_period_days": 30,
            }
        }
    }


class FamilyUsageTrackingRequest(BaseDocumentedModel):
    """
    Request model for querying family usage tracking data.
    """

    start_date: Optional[datetime] = Field(None, description="Start date for usage tracking query")
    end_date: Optional[datetime] = Field(None, description="End date for usage tracking query")
    include_billing_metrics: bool = Field(True, description="Whether to include billing-related metrics")
    granularity: str = Field("daily", description="Granularity of usage data (daily, weekly, monthly)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-01-31T23:59:59Z",
                "include_billing_metrics": True,
                "granularity": "daily",
            }
        }
    }


class UpdateFamilyLimitsResponse(BaseDocumentedModel):
    """
    Response model for family limits update operations.
    """

    user_id: str = Field(..., description="User ID whose limits were updated")
    previous_limits: Dict[str, Any] = Field(..., description="Previous limit values")
    new_limits: Dict[str, Any] = Field(..., description="New limit values")
    effective_date: datetime = Field(..., description="When the new limits took effect")
    grace_period_expires: Optional[datetime] = Field(None, description="When grace period expires")
    updated_by: str = Field(..., description="Who updated the limits")
    updated_at: datetime = Field(..., description="When the update was performed")
    audit_log_id: str = Field(..., description="Audit log entry ID")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user_1234567890abcdef",
                "previous_limits": {"max_families_allowed": 1, "max_members_per_family": 5},
                "new_limits": {"max_families_allowed": 3, "max_members_per_family": 10},
                "effective_date": "2024-01-01T00:00:00Z",
                "grace_period_expires": "2024-01-31T23:59:59Z",
                "updated_by": "admin_user_123",
                "updated_at": "2024-01-01T00:00:00Z",
                "audit_log_id": "audit_1234567890abcdef",
            }
        }
    }


class FamilyUsageTrackingResponse(BaseDocumentedModel):
    """
    Response model for family usage tracking data.
    """

    user_id: str = Field(..., description="User ID for the usage data")
    period_start: datetime = Field(..., description="Start of tracking period")
    period_end: datetime = Field(..., description="End of tracking period")
    usage_data: List[Dict[str, Any]] = Field(..., description="Usage data points")
    billing_metrics: Optional[BillingUsageMetrics] = Field(None, description="Billing metrics")
    summary: Dict[str, Any] = Field(..., description="Usage summary")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user_1234567890abcdef",
                "period_start": "2024-01-01T00:00:00Z",
                "period_end": "2024-01-31T23:59:59Z",
                "usage_data": [
                    {"date": "2024-01-01", "families_count": 1, "total_members": 3, "events": ["family_created"]}
                ],
                "billing_metrics": {
                    "period_start": "2024-01-01T00:00:00Z",
                    "period_end": "2024-01-31T23:59:59Z",
                    "peak_families": 1,
                    "peak_members_total": 4,
                    "average_families": 1.0,
                    "average_members_total": 3.5,
                    "family_creation_events": 1,
                    "member_addition_events": 1,
                    "upgrade_recommendations": [],
                },
                "summary": {
                    "total_families_created": 1,
                    "total_members_added": 1,
                    "peak_usage_day": "2024-01-15",
                    "upgrade_recommended": False,
                },
            }
        }
    }


class UsageDataPoint(BaseModel):
    """Model for individual usage data points."""

    date: datetime = Field(..., description="Date of the usage data point")
    families_count: int = Field(..., description="Number of families on this date")
    total_members: int = Field(..., description="Total members across all families")
    events: List[str] = Field(default_factory=list, description="Events that occurred on this date")
    daily_activity_score: float = Field(0.0, description="Activity score for the day")


class UsageTrackingSummary(BaseModel):
    """Model for usage tracking summary statistics."""

    total_families_created: int = Field(..., description="Total families created in period")
    total_members_added: int = Field(..., description="Total members added in period")
    peak_usage_day: Optional[str] = Field(None, description="Date with highest usage")
    average_daily_families: float = Field(..., description="Average families per day")
    average_daily_members: float = Field(..., description="Average members per day")
    upgrade_recommended: bool = Field(..., description="Whether upgrade is recommended")
    usage_trend: str = Field(..., description="Usage trend: 'increasing', 'stable', 'decreasing'")


class UsageTrackingResponse(BaseDocumentedModel):
    """
    Response model for family usage tracking data.

    Provides comprehensive usage metrics for billing integration and analytics.
    """

    user_id: str = Field(..., description="User ID for the tracking data")
    period_start: datetime = Field(..., description="Start of tracking period")
    period_end: datetime = Field(..., description="End of tracking period")
    granularity: str = Field(..., description="Data granularity (daily, weekly, monthly)")

    usage_data: List[UsageDataPoint] = Field(..., description="Usage data points for the specified period")

    billing_metrics: BillingUsageMetrics = Field(..., description="Billing-related usage metrics")

    summary: UsageTrackingSummary = Field(..., description="Summary statistics for the tracking period")

    current_limits: Dict[str, Any] = Field(..., description="Current user limits for context")

    recommendations: List[str] = Field(default_factory=list, description="Usage-based recommendations")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "period_start": "2024-01-01T00:00:00Z",
                "period_end": "2024-01-31T23:59:59Z",
                "granularity": "daily",
                "usage_data": [
                    {
                        "date": "2024-01-01T00:00:00Z",
                        "families_count": 1,
                        "total_members": 3,
                        "events": ["family_created", "member_added"],
                        "daily_activity_score": 8.5,
                    }
                ],
                "billing_metrics": {
                    "period_start": "2024-01-01T00:00:00Z",
                    "period_end": "2024-01-31T23:59:59Z",
                    "peak_families": 1,
                    "peak_members_total": 5,
                    "average_families": 1.0,
                    "average_members_total": 4.2,
                    "family_creation_events": 1,
                    "member_addition_events": 2,
                    "upgrade_recommendations": ["Consider Pro plan for unlimited families"],
                },
                "summary": {
                    "total_families_created": 1,
                    "total_members_added": 2,
                    "peak_usage_day": "2024-01-15",
                    "average_daily_families": 1.0,
                    "average_daily_members": 4.2,
                    "upgrade_recommended": False,
                    "usage_trend": "stable",
                },
                "current_limits": {"max_families_allowed": 1, "max_members_per_family": 5, "current_families": 1},
                "recommendations": ["Your usage is within limits", "Consider upgrading for unlimited families"],
            }
        }
    }


class LimitEnforcementStatus(BaseModel):
    """Model for individual limit enforcement status."""

    limit_type: str = Field(..., description="Type of limit being enforced")
    is_enforced: bool = Field(..., description="Whether limit is currently enforced")
    current_value: int = Field(..., description="Current usage value")
    limit_value: int = Field(..., description="Limit threshold value")
    is_compliant: bool = Field(..., description="Whether current usage is compliant")
    grace_period_active: bool = Field(False, description="Whether grace period is active")
    grace_period_expires: Optional[datetime] = Field(None, description="When grace period expires")
    enforcement_action: str = Field(..., description="Action taken when limit exceeded")


class FamilyValidationResult(BaseModel):
    """Model for family validation against limits."""

    family_id: str = Field(..., description="Family identifier")
    family_name: str = Field(..., description="Family name")
    is_compliant: bool = Field(..., description="Whether family is compliant with limits")
    current_members: int = Field(..., description="Current member count")
    member_limit: int = Field(..., description="Member limit for this family")
    violations: List[str] = Field(default_factory=list, description="List of limit violations")
    recommended_actions: List[str] = Field(default_factory=list, description="Recommended actions")


class LimitEnforcementResponse(BaseDocumentedModel):
    """
    Response model for limit enforcement status.

    Provides detailed information about current limit enforcement and compliance.
    """

    user_id: str = Field(..., description="User ID")
    overall_compliance: bool = Field(..., description="Overall compliance status")
    enforcement_active: bool = Field(..., description="Whether enforcement is active")

    limit_statuses: List[LimitEnforcementStatus] = Field(..., description="Status for each type of limit")

    family_validations: List[FamilyValidationResult] = Field(..., description="Validation results for each family")

    grace_periods: Dict[str, Any] = Field(..., description="Active grace periods information")

    compliance_summary: Dict[str, Any] = Field(..., description="Summary of compliance status")

    recommendations: List[str] = Field(default_factory=list, description="Compliance recommendations")

    last_updated: datetime = Field(..., description="When status was last updated")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "overall_compliance": True,
                "enforcement_active": True,
                "limit_statuses": [
                    {
                        "limit_type": "families",
                        "is_enforced": True,
                        "current_value": 1,
                        "limit_value": 1,
                        "is_compliant": True,
                        "grace_period_active": False,
                        "grace_period_expires": None,
                        "enforcement_action": "block_creation",
                    }
                ],
                "family_validations": [
                    {
                        "family_id": "fam_1234567890abcdef",
                        "family_name": "Smith Family",
                        "is_compliant": True,
                        "current_members": 4,
                        "member_limit": 5,
                        "violations": [],
                        "recommended_actions": [],
                    }
                ],
                "grace_periods": {"active_periods": [], "expired_periods": []},
                "compliance_summary": {
                    "total_families": 1,
                    "compliant_families": 1,
                    "total_violations": 0,
                    "grace_periods_active": 0,
                },
                "recommendations": ["All limits are compliant", "No action required"],
                "last_updated": "2024-01-15T12:00:00Z",
            }
        }
    }


class DirectTransferRequest(BaseDocumentedModel):
    """
    Request model for direct SBD token transfer from family account.

    Allows family administrators to directly transfer tokens from the family
    account to any user or external account. Bypasses the normal request/approval
    workflow for immediate transfers.
    """

    recipient_identifier: str = Field(
        ..., description="Username or user ID of the recipient", json_schema_extra={"example": "john_doe"}
    )
    amount: int = Field(..., gt=0, description="Amount of SBD tokens to transfer", json_schema_extra={"example": 500})
    reason: str = Field(
        ...,
        max_length=TOKEN_REQUEST_REASON_MAX_LENGTH,
        description="Reason for the direct transfer",
        json_schema_extra={"example": "Emergency funds for school supplies"},
    )
    recipient_type: str = Field(
        "user",
        description="Type of recipient: 'user' for internal users, 'external' for external accounts",
        json_schema_extra={"example": "user"},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "recipient_identifier": "john_doe",
                "amount": 500,
                "reason": "Emergency funds for school supplies",
                "recipient_type": "user",
            }
        }
    }

    @field_validator("recipient_type")
    @classmethod
    def validate_recipient_type(cls, v: str) -> str:
        """Validate that the recipient type is supported."""
        if v.lower() not in ["user", "external"]:
            logger.error("Invalid recipient type: %s", v)
            raise ValueError("Recipient type must be either 'user' or 'external'")
        return v.lower()


class DirectTransferResponse(BaseDocumentedModel):
    """
    Response model for direct SBD token transfer.
    """

    transfer_id: str = Field(
        ..., description="Unique transfer identifier", json_schema_extra={"example": "xfer_1234567890abcdef"}
    )
    family_id: str = Field(..., description="Family identifier", json_schema_extra={"example": "fam_1234567890abcdef"})
    recipient_identifier: str = Field(
        ..., description="Recipient username or ID", json_schema_extra={"example": "john_doe"}
    )
    amount: int = Field(..., description="Amount transferred", json_schema_extra={"example": 500})
    reason: str = Field(
        ..., description="Transfer reason", json_schema_extra={"example": "Emergency funds for school supplies"}
    )
    transferred_by: str = Field(
        ...,
        description="User ID of admin who performed transfer",
        json_schema_extra={"example": "507f1f77bcf86cd799439011"},
    )
    transferred_by_username: str = Field(
        ..., description="Username of admin who performed transfer", json_schema_extra={"example": "jane_smith"}
    )
    transferred_at: datetime = Field(
        ...,
        description="UTC timestamp when transfer was completed",
        json_schema_extra={"example": "2024-01-01T12:00:00Z"},
    )
    transaction_id: Optional[str] = Field(
        None, description="Blockchain transaction ID", json_schema_extra={"example": "txn_abcdef1234567890"}
    )
    message: str = Field(
        ..., description="Success message", json_schema_extra={"example": "Direct transfer completed successfully"}
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "transfer_id": "xfer_1234567890abcdef",
                "family_id": "fam_1234567890abcdef",
                "recipient_identifier": "john_doe",
                "amount": 500,
                "reason": "Emergency funds for school supplies",
                "transferred_by": "507f1f77bcf86cd799439011",
                "transferred_by_username": "jane_smith",
                "transferred_at": "2024-01-01T12:00:00Z",
                "transaction_id": "txn_abcdef1234567890",
                "message": "Direct transfer completed successfully",
            }
        }
    }
