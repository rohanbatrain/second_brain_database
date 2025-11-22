"""
Pydantic models for multi-tenancy management.

This module contains all request/response models, validation schemas,
and data transfer objects for the tenant management functionality.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# Constants for validation
TENANT_PLANS = ["free", "pro", "enterprise"]
TENANT_STATUSES = ["active", "suspended", "trial", "cancelled"]
TENANT_ROLES = ["owner", "admin", "member", "viewer"]
MEMBERSHIP_STATUSES = ["active", "invited", "suspended"]


# Request Models
class CreateTenantRequest(BaseModel):
    """Request model for creating a new tenant."""

    name: str = Field(..., min_length=2, max_length=100, description="Tenant name")
    slug: Optional[str] = Field(None, min_length=2, max_length=50, description="URL-friendly identifier")
    plan: Literal["free", "pro", "enterprise"] = Field("free", description="Subscription plan")
    description: Optional[str] = Field(None, max_length=500, description="Tenant description")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        if v is not None:
            v = v.strip().lower()
            if not v.replace("-", "").replace("_", "").isalnum():
                raise ValueError("Slug must contain only alphanumeric characters, dashes, and underscores")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Tenant name cannot be empty")
        return v


class UpdateTenantRequest(BaseModel):
    """Request model for updating tenant information."""

    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    plan: Optional[Literal["free", "pro", "enterprise"]] = None
    status: Optional[Literal["active", "suspended", "trial", "cancelled"]] = None


class InviteUserToTenantRequest(BaseModel):
    """Request model for inviting a user to a tenant."""

    user_id: str = Field(..., description="ID of the user to invite")
    role: Literal["admin", "member", "viewer"] = Field("member", description="Role to assign")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v == "owner":
            raise ValueError("Cannot invite users as owner. Transfer ownership instead.")
        return v


class UpdateMembershipRequest(BaseModel):
    """Request model for updating tenant membership."""

    role: Optional[Literal["admin", "member", "viewer"]] = None
    permissions: Optional[Dict[str, bool]] = None


class SwitchTenantRequest(BaseModel):
    """Request model for switching active tenant."""

    tenant_id: str = Field(..., description="ID of the tenant to switch to")


# Response Models
class TenantSettingsResponse(BaseModel):
    """Response model for tenant settings."""

    max_users: int
    max_storage_gb: int
    features_enabled: List[str]
    custom_domain: Optional[str] = None


class TenantBillingResponse(BaseModel):
    """Response model for tenant billing information."""

    subscription_id: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None


class TenantResponse(BaseModel):
    """Response model for tenant information."""

    tenant_id: str
    name: str
    slug: str
    plan: str
    status: str
    description: Optional[str] = None
    owner_user_id: str
    settings: TenantSettingsResponse
    billing: TenantBillingResponse
    member_count: int = 0
    created_at: datetime
    updated_at: datetime


class TenantMembershipPermissionsResponse(BaseModel):
    """Response model for membership permissions."""

    can_invite_users: bool
    can_manage_billing: bool
    can_access_audit_logs: bool


class TenantMembershipResponse(BaseModel):
    """Response model for tenant membership information."""

    membership_id: str
    tenant_id: str
    tenant_name: str
    user_id: str
    role: str
    status: str
    permissions: TenantMembershipPermissionsResponse
    invited_by: Optional[str] = None
    invited_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None


class TenantMemberResponse(BaseModel):
    """Response model for a member within a tenant."""

    user_id: str
    username: str
    email: str
    role: str
    status: str
    joined_at: Optional[datetime] = None


class TenantListResponse(BaseModel):
    """Response model for listing tenants."""

    tenants: List[TenantResponse]
    total_count: int


class TenantMembersListResponse(BaseModel):
    """Response model for listing tenant members."""

    members: List[TenantMemberResponse]
    total_count: int


class TenantLimitsResponse(BaseModel):
    """Response model for tenant resource limits."""

    plan: str
    max_users: int
    max_storage_gb: int
    current_users: int
    current_storage_gb: float
    features_enabled: List[str]
    can_upgrade: bool
    upgrade_required_for: List[str] = []


# Database Schema Models
class TenantDocument(BaseModel):
    """Database document model for tenants collection."""

    tenant_id: str
    name: str
    slug: str
    plan: str
    status: str
    description: Optional[str] = None
    owner_user_id: str
    settings: Dict[str, Any]
    billing: Dict[str, Any]
    member_count: int = 0
    created_at: datetime
    updated_at: datetime

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v):
        if v not in TENANT_PLANS:
            raise ValueError(f"Invalid plan: {v}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in TENANT_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v


class TenantMembershipDocument(BaseModel):
    """Database document model for tenant_memberships collection."""

    membership_id: str
    tenant_id: str
    user_id: str
    role: str
    status: str
    permissions: Dict[str, bool]
    invited_by: Optional[str] = None
    invited_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in TENANT_ROLES:
            raise ValueError(f"Invalid role: {v}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in MEMBERSHIP_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v
