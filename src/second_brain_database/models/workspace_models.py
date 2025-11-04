"""
Pydantic models for the fully-featured Teams/Workspaces feature.
"""
from datetime import datetime
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field

class WorkspaceMember(BaseModel):
    """Defines a user's membership and role within a workspace."""
    user_id: str = Field(..., description="The ID of the user.")
    # Full-featured roles for granular permissions
    role: Literal["admin", "editor", "viewer"] = Field(
        "viewer",
        description="The role of the user within the workspace."
    )
    joined_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of when the member joined.")

class WorkspaceSettings(BaseModel):
    """Defines settings for a workspace."""
    allow_member_invites: bool = Field(
        True,
        description="Determines if non-admin members can invite others (as viewers)."
    )
    default_new_member_role: Literal["editor", "viewer"] = Field(
        "viewer",
        description="The default role assigned to newly invited members."
    )

class WorkspaceSBDAccount(BaseModel):
    """SBD account configuration for workspace shared token management."""
    account_username: str = Field(
        default="",
        description="Virtual account username for the workspace"
    )
    is_frozen: bool = Field(
        default=False,
        description="Whether the account is currently frozen"
    )
    frozen_by: Optional[str] = Field(
        None,
        description="Username of admin who froze the account"
    )
    frozen_at: Optional[datetime] = Field(
        None,
        description="When the account was frozen"
    )
    spending_permissions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Spending permissions for all workspace members"
    )
    notification_settings: Dict[str, Any] = Field(
        default_factory=lambda: {
            "notify_on_spend": True,
            "notify_on_deposit": True,
            "large_transaction_threshold": 1000,
            "notify_admins_only": False
        },
        description="Notification settings for SBD transactions"
    )

class WorkspaceDocument(BaseModel):
    """Database document model for the workspaces collection."""
    workspace_id: str = Field(..., description="Unique identifier for the workspace.")
    name: str = Field(..., max_length=100, description="The name of the workspace.")
    description: Optional[str] = Field(None, max_length=500, description="A brief description of the workspace.")
    owner_id: str = Field(..., description="The user ID of the workspace owner, who has ultimate control.")
    members: List[WorkspaceMember] = Field(..., description="List of members in the workspace.")
    settings: WorkspaceSettings = Field(default_factory=WorkspaceSettings, description="Settings for the workspace.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # SBD account information for team wallet functionality
    sbd_account: WorkspaceSBDAccount = Field(
        default_factory=WorkspaceSBDAccount,
        description="SBD account configuration for shared token management"
    )
