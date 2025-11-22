"""
Tenant management models for multi-tenancy support.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TenantPlan(str, Enum):
    """Available tenant subscription plans."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class TenantMemberRole(str, Enum):
    """Roles for tenant members."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    GUEST = "guest"


class TenantMembership(BaseModel):
    """Tenant membership information."""
    tenant_id: str
    role: TenantMemberRole
    joined_at: datetime = Field(default_factory=datetime.utcnow)


class CreateTenantRequest(BaseModel):
    """Request model for creating a new tenant."""
    name: str = Field(..., min_length=1, max_length=100, description="Tenant name")
    slug: str = Field(..., min_length=1, max_length=50, description="Tenant slug (URL-safe identifier)")
    plan: TenantPlan = Field(default=TenantPlan.FREE, description="Subscription plan")
    description: Optional[str] = Field(None, max_length=500, description="Tenant description")


class SwitchTenantRequest(BaseModel):
    """Request model for switching active tenant."""
    tenant_id: str = Field(..., description="Target tenant ID to switch to")


class TenantResponse(BaseModel):
    """Response model for tenant information."""
    tenant_id: str
    name: str
    slug: str
    plan: TenantPlan
    description: Optional[str]
    owner_user_id: str
    member_count: int
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    
    # Resource limits based on plan
    max_users: int
    max_storage_gb: int
    max_api_calls_per_day: int


class TenantMemberResponse(BaseModel):
    """Response model for tenant member information."""
    user_id: str
    username: str
    email: str
    role: TenantMemberRole
    joined_at: datetime


class AddTenantMemberRequest(BaseModel):
    """Request model for adding a member to a tenant."""
    user_id: str = Field(..., description="User ID to add")
    role: TenantMemberRole = Field(default=TenantMemberRole.MEMBER, description="Member role")


class UpdateTenantRequest(BaseModel):
    """Request model for updating tenant information."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    plan: Optional[TenantPlan] = None
