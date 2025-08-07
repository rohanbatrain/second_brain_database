"""
Pydantic models for family management system.

This module contains all request/response models, validation schemas,
and data transfer objects for the family management functionality.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, EmailStr, Field, validator


# Constants for validation
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

NOTIFICATION_TYPES = [
    "sbd_spend", "sbd_deposit", "large_transaction", "spending_limit_reached",
    "account_frozen", "account_unfrozen", "admin_promoted", "admin_demoted",
    "member_added", "member_removed", "token_request_created", 
    "token_request_approved", "token_request_denied", "permissions_updated"
]


# Request Models
class CreateFamilyRequest(BaseModel):
    """Request model for creating a new family."""
    name: Optional[str] = Field(None, max_length=100, description="Optional custom family name")
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                return None
            if len(v) < 2:
                raise ValueError("Family name must be at least 2 characters long")
            # Prevent reserved prefixes
            if v.lower().startswith(('family_', 'team_', 'admin_', 'system_')):
                raise ValueError("Family name cannot start with reserved prefixes")
        return v


class InviteMemberRequest(BaseModel):
    """Request model for inviting a family member."""
    identifier: str = Field(..., description="Email address or username of the user to invite")
    identifier_type: Literal["email", "username"] = Field("email", description="Type of identifier provided")
    relationship_type: str = Field(..., description="Relationship type from inviter's perspective")
    
    @validator('identifier')
    def validate_identifier(cls, v):
        v = v.strip().lower()
        if not v:
            raise ValueError("Identifier cannot be empty")
        return v
    
    @validator('relationship_type')
    def validate_relationship_type(cls, v):
        v = v.lower().strip()
        if v not in RELATIONSHIP_TYPES:
            valid_types = ", ".join(RELATIONSHIP_TYPES.keys())
            raise ValueError(f"Invalid relationship type. Valid types: {valid_types}")
        return v


class RespondToInvitationRequest(BaseModel):
    """Request model for responding to a family invitation."""
    action: Literal["accept", "decline"] = Field(..., description="Action to take on the invitation")


class UpdateRelationshipRequest(BaseModel):
    """Request model for updating a family relationship."""
    relationship_type_a_to_b: str = Field(..., description="Relationship type from user A to user B")
    relationship_type_b_to_a: str = Field(..., description="Relationship type from user B to user A")
    
    @validator('relationship_type_a_to_b', 'relationship_type_b_to_a')
    def validate_relationship_types(cls, v):
        v = v.lower().strip()
        if v not in RELATIONSHIP_TYPES:
            valid_types = ", ".join(RELATIONSHIP_TYPES.keys())
            raise ValueError(f"Invalid relationship type. Valid types: {valid_types}")
        return v


class UpdateSpendingPermissionsRequest(BaseModel):
    """Request model for updating family member spending permissions."""
    user_id: str = Field(..., description="ID of the user to update permissions for")
    spending_limit: int = Field(..., ge=-1, description="Spending limit (-1 for unlimited)")
    can_spend: bool = Field(..., description="Whether the user can spend from family account")
    
    @validator('spending_limit')
    def validate_spending_limit(cls, v):
        if v < -1:
            raise ValueError("Spending limit must be -1 (unlimited) or a positive number")
        return v


class FreezeAccountRequest(BaseModel):
    """Request model for freezing/unfreezing family SBD account."""
    action: Literal["freeze", "unfreeze"] = Field(..., description="Action to take on the account")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for freezing the account")
    
    @validator('reason')
    def validate_reason(cls, v, values):
        if values.get('action') == 'freeze' and not v:
            raise ValueError("Reason is required when freezing an account")
        return v.strip() if v else None


class CreateTokenRequestRequest(BaseModel):
    """Request model for creating a token request."""
    amount: int = Field(..., gt=0, description="Amount of tokens requested")
    reason: str = Field(..., max_length=500, description="Reason for the token request")
    
    @validator('reason')
    def validate_reason(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Reason cannot be empty")
        if len(v) < 5:
            raise ValueError("Reason must be at least 5 characters long")
        return v


class ReviewTokenRequestRequest(BaseModel):
    """Request model for reviewing a token request."""
    action: Literal["approve", "deny"] = Field(..., description="Action to take on the request")
    comments: Optional[str] = Field(None, max_length=1000, description="Admin comments on the decision")
    
    @validator('comments')
    def validate_comments(cls, v):
        return v.strip() if v else None


class AdminActionRequest(BaseModel):
    """Request model for admin promotion/demotion."""
    action: Literal["promote", "demote"] = Field(..., description="Action to take")


class UpdateNotificationPreferencesRequest(BaseModel):
    """Request model for updating notification preferences."""
    email_notifications: bool = Field(True, description="Enable email notifications")
    push_notifications: bool = Field(True, description="Enable push notifications")
    sms_notifications: bool = Field(False, description="Enable SMS notifications")
    notify_on_spend: bool = Field(True, description="Notify on family spending")
    notify_on_deposit: bool = Field(True, description="Notify on family deposits")
    large_transaction_threshold: int = Field(1000, ge=0, description="Threshold for large transaction alerts")


class MarkNotificationsReadRequest(BaseModel):
    """Request model for marking notifications as read."""
    notification_ids: List[str] = Field(..., description="List of notification IDs to mark as read")
    
    @validator('notification_ids')
    def validate_notification_ids(cls, v):
        if not v:
            raise ValueError("At least one notification ID must be provided")
        return v


# Response Models
class SpendingPermissionsResponse(BaseModel):
    """Response model for spending permissions."""
    role: str
    spending_limit: int
    can_spend: bool
    updated_by: str
    updated_at: datetime


class SBDAccountResponse(BaseModel):
    """Response model for family SBD account information."""
    account_username: str
    balance: int
    is_frozen: bool
    frozen_by: Optional[str] = None
    frozen_at: Optional[datetime] = None
    spending_permissions: Dict[str, SpendingPermissionsResponse]
    notification_settings: Dict[str, Any]
    recent_transactions: List[Dict[str, Any]] = []


class FamilySettingsResponse(BaseModel):
    """Response model for family settings."""
    allow_member_invites: bool
    visibility: str
    auto_approval_threshold: int
    request_expiry_hours: int


class SuccessionPlanResponse(BaseModel):
    """Response model for succession plan."""
    backup_admins: List[str]
    recovery_contacts: List[str]


class FamilyResponse(BaseModel):
    """Response model for family information."""
    family_id: str
    name: str
    admin_user_ids: List[str]
    member_count: int
    created_at: datetime
    updated_at: datetime
    is_active: bool
    is_admin: bool
    user_role: str
    sbd_account: SBDAccountResponse
    settings: FamilySettingsResponse
    succession_plan: SuccessionPlanResponse
    usage_stats: Dict[str, Any] = {}


class RelationshipResponse(BaseModel):
    """Response model for family relationship information."""
    relationship_id: str
    related_user_id: str
    related_username: str
    relationship_type: str
    created_at: datetime
    activated_at: Optional[datetime] = None


class FamilyMemberResponse(BaseModel):
    """Response model for family member information."""
    user_id: str
    username: str
    email: str
    role: str
    joined_at: datetime
    spending_permissions: SpendingPermissionsResponse
    relationships: List[RelationshipResponse] = []
    is_active: bool = True


class InvitationResponse(BaseModel):
    """Response model for family invitation information."""
    invitation_id: str
    family_id: str
    family_name: str
    inviter_user_id: str
    inviter_username: str
    invitee_email: str
    invitee_username: str
    relationship_type: str
    status: str
    expires_at: datetime
    created_at: datetime
    responded_at: Optional[datetime] = None
    email_sent: bool
    email_sent_at: Optional[datetime] = None


class TokenRequestResponse(BaseModel):
    """Response model for token request information."""
    request_id: str
    family_id: str
    requester_user_id: str
    requester_username: str
    amount: int
    reason: str
    status: str
    reviewed_by: Optional[str] = None
    admin_comments: Optional[str] = None
    auto_approved: bool
    created_at: datetime
    expires_at: datetime
    reviewed_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None


class NotificationResponse(BaseModel):
    """Response model for family notification information."""
    notification_id: str
    family_id: str
    type: str
    title: str
    message: str
    data: Dict[str, Any] = {}
    status: str
    created_at: datetime
    sent_at: Optional[datetime] = None
    is_read: bool
    read_at: Optional[datetime] = None


class FamilyUsageResponse(BaseModel):
    """Response model for family usage information."""
    family_id: str
    family_name: str
    member_count: int
    max_members: int
    role: str
    created_at: datetime


class FamilyLimitsResponse(BaseModel):
    """Response model for family limits information."""
    max_families_allowed: int
    max_members_per_family: int
    current_families: int
    families_usage: List[FamilyUsageResponse]
    can_create_family: bool
    upgrade_required: bool
    upgrade_message: Optional[str] = None


class FamilyStatsResponse(BaseModel):
    """Response model for family statistics."""
    total_families: int
    total_members: int
    total_relationships: int
    total_invitations_sent: int
    total_invitations_accepted: int
    total_token_requests: int
    total_sbd_transactions: int
    average_family_size: float
    most_common_relationships: List[Dict[str, Any]]


class DatabaseMigrationResponse(BaseModel):
    """Response model for database migration operations."""
    migration_id: str
    operation: str
    status: str
    collections_affected: List[str]
    records_processed: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    rollback_available: bool


class BackupResponse(BaseModel):
    """Response model for database backup operations."""
    backup_id: str
    backup_type: str
    collections: List[str]
    file_path: str
    file_size: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    status: str
    checksum: str


# Database Schema Models (for internal use)
class FamilyDocument(BaseModel):
    """Database document model for families collection."""
    family_id: str
    name: str
    admin_user_ids: List[str]
    created_at: datetime
    updated_at: datetime
    member_count: int
    is_active: bool
    sbd_account: Dict[str, Any]
    settings: Dict[str, Any]
    succession_plan: Dict[str, Any]


class FamilyRelationshipDocument(BaseModel):
    """Database document model for family_relationships collection."""
    relationship_id: str
    family_id: str
    user_a_id: str
    user_b_id: str
    relationship_type_a_to_b: str
    relationship_type_b_to_a: str
    status: str
    created_by: str
    created_at: datetime
    activated_at: Optional[datetime] = None
    updated_at: datetime


class FamilyInvitationDocument(BaseModel):
    """Database document model for family_invitations collection."""
    invitation_id: str
    family_id: str
    inviter_user_id: str
    invitee_email: str
    invitee_user_id: str
    relationship_type: str
    invitation_token: str
    status: str
    expires_at: datetime
    created_at: datetime
    responded_at: Optional[datetime] = None
    email_sent: bool
    email_sent_at: Optional[datetime] = None


class FamilyNotificationDocument(BaseModel):
    """Database document model for family_notifications collection."""
    notification_id: str
    family_id: str
    recipient_user_ids: List[str]
    type: str
    title: str
    message: str
    data: Dict[str, Any]
    status: str
    created_at: datetime
    sent_at: Optional[datetime] = None
    read_by: Dict[str, datetime] = {}


class FamilyTokenRequestDocument(BaseModel):
    """Database document model for family_token_requests collection."""
    request_id: str
    family_id: str
    requester_user_id: str
    amount: int
    reason: str
    status: str
    reviewed_by: Optional[str] = None
    admin_comments: Optional[str] = None
    auto_approved: bool
    created_at: datetime
    expires_at: datetime
    reviewed_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None


# Error Response Models
class FamilyErrorResponse(BaseModel):
    """Error response model for family operations."""
    error: Dict[str, Any]
    
    class Config:
        schema_extra = {
            "example": {
                "error": {
                    "code": "FAMILY_LIMIT_EXCEEDED",
                    "message": "You have reached the maximum number of families allowed",
                    "details": {
                        "current_families": 1,
                        "max_families": 1
                    },
                    "upgrade_info": {
                        "required_plan": "premium",
                        "upgrade_url": "/upgrade"
                    },
                    "suggested_actions": [
                        "Upgrade to premium plan",
                        "Delete an existing family"
                    ]
                }
            }
        }


class ValidationErrorResponse(BaseModel):
    """Validation error response model."""
    detail: List[Dict[str, Any]]
    
    class Config:
        schema_extra = {
            "example": {
                "detail": [
                    {
                        "loc": ["body", "relationship_type"],
                        "msg": "Invalid relationship type. Valid types: parent, child, sibling, spouse, grandparent, grandchild, uncle, aunt, nephew, niece, cousin",
                        "type": "value_error"
                    }
                ]
            }
        }