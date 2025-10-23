"""
Pydantic models for the fully-featured Teams/Workspaces feature.
"""
from datetime import datetime
from typing import List, Literal, Optional
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
