"""
Workspace Management MCP Tools

MCP tools for comprehensive workspace lifecycle management, member operations,
and team management using existing WorkspaceManager patterns.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ....config import settings
from ....managers.logging_manager import get_logger
from ....managers.team_wallet_manager import TeamWalletManager
from ....managers.workspace_manager import WorkspaceManager
from ..context import create_mcp_audit_trail
from ..exceptions import MCPAuthorizationError, MCPValidationError
from ..modern_server import mcp
from ..security import authenticated_tool, get_mcp_user_context

logger = get_logger(prefix="[MCP_WorkspaceTools]")

# Import manager instances
from ....database import db_manager
from ....managers.redis_manager import redis_manager
from ....managers.security_manager import security_manager


# Pydantic models for MCP tool parameters and responses
class WorkspaceInfo(BaseModel):
    """Workspace information response model."""

    workspace_id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    owner_id: str
    member_count: int
    settings: Dict[str, Any] = Field(default_factory=dict)
    sbd_account: Dict[str, Any] = Field(default_factory=dict)


class WorkspaceMember(BaseModel):
    """Workspace member information model."""

    user_id: str
    role: str
    joined_at: datetime


class WorkspaceCreateRequest(BaseModel):
    """Request model for workspace creation."""

    name: str = Field(..., description="Workspace name")
    description: Optional[str] = Field(None, description="Workspace description")


class WorkspaceUpdateRequest(BaseModel):
    """Request model for workspace update."""

    name: Optional[str] = Field(None, description="New workspace name")
    description: Optional[str] = Field(None, description="New workspace description")
    settings: Optional[Dict[str, Any]] = Field(None, description="Workspace settings")


# Core Workspace Management Tools (Task 7.1)


@authenticated_tool(
    name="get_user_workspaces",
    description="Get all workspaces that the current user is a member of",
    permissions=["workspace:read"],
    rate_limit_action="workspace_read",
)
async def get_user_workspaces() -> List[Dict[str, Any]]:
    """
    Get all workspaces that the current user is a member of with their roles.

    Returns:
        List of workspaces the user belongs to with role information
    """
    user_context = get_mcp_user_context()

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)

    try:
        # Get user's workspaces using existing manager
        workspaces = await workspace_manager.get_workspaces_for_user(user_context.user_id)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_user_workspaces",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"workspace_count": len(workspaces)},
        )

        # Format response
        result = []
        for workspace in workspaces:
            # Get user's role in this workspace
            user_role = workspace_manager.get_user_role(user_context.user_id, workspace)

            workspace_info = {
                "workspace_id": workspace.get("workspace_id"),
                "name": workspace.get("name"),
                "description": workspace.get("description"),
                "created_at": workspace.get("created_at"),
                "updated_at": workspace.get("updated_at"),
                "owner_id": workspace.get("owner_id"),
                "user_role": user_role,
                "member_count": len(workspace.get("members", [])),
                "settings": workspace.get("settings", {}),
                "sbd_account": workspace.get("sbd_account", {}),
            }
            result.append(workspace_info)

        logger.info("Retrieved %d workspaces for user %s", len(result), user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to get user workspaces for %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to retrieve user workspaces: {str(e)}")


@authenticated_tool(
    name="create_workspace",
    description="Create a new workspace with the current user as owner",
    permissions=["workspace:create"],
    rate_limit_action="workspace_create",
)
async def create_workspace(name: str, description: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new workspace with the current user as the owner/administrator.

    Args:
        name: Name for the workspace
        description: Optional description for the workspace

    Returns:
        Dictionary containing the created workspace information

    Raises:
        MCPValidationError: If workspace creation fails or limits are exceeded
    """
    user_context = get_mcp_user_context()

    # Validate input
    if not name or len(name.strip()) < 3:
        raise MCPValidationError("Workspace name must be at least 3 characters long")

    if len(name.strip()) > 100:
        raise MCPValidationError("Workspace name cannot exceed 100 characters")

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)

    try:
        # Create workspace using existing manager
        workspace_result = await workspace_manager.create_workspace(
            user_id=user_context.user_id, name=name.strip(), description=description.strip() if description else None
        )

        workspace_id = workspace_result.get("workspace_id")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="create_workspace",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            changes={"name": name, "description": description},
            metadata={"owner_id": user_context.user_id},
        )

        logger.info("Created workspace %s for user %s", workspace_id, user_context.user_id)
        return workspace_result

    except Exception as e:
        logger.error("Failed to create workspace for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to create workspace: {str(e)}")


@authenticated_tool(
    name="get_workspace_details",
    description="Get detailed information about a specific workspace",
    permissions=["workspace:read"],
    rate_limit_action="workspace_read",
)
async def get_workspace_details(workspace_id: str) -> Dict[str, Any]:
    """
    Get comprehensive workspace information including members, settings, and SBD account details.

    Args:
        workspace_id: The ID of the workspace to retrieve information for

    Returns:
        Dictionary containing workspace information, member details, and account information

    Raises:
        MCPAuthorizationError: If user doesn't have access to the workspace
        MCPValidationError: If workspace_id is invalid
    """
    user_context = get_mcp_user_context()

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)

    try:
        # Get workspace details using existing manager (validates membership)
        workspace = await workspace_manager.get_workspace_by_id(workspace_id, user_context.user_id)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_workspace_details",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={"workspace_name": workspace.get("name")},
        )

        # Format response with comprehensive information
        result = {
            "workspace_id": workspace.get("workspace_id"),
            "name": workspace.get("name"),
            "description": workspace.get("description"),
            "created_at": workspace.get("created_at"),
            "updated_at": workspace.get("updated_at"),
            "owner_id": workspace.get("owner_id"),
            "members": workspace.get("members", []),
            "member_count": len(workspace.get("members", [])),
            "settings": workspace.get("settings", {}),
            "sbd_account": workspace.get("sbd_account", {}),
            "user_role": workspace_manager.get_user_role(user_context.user_id, workspace),
        }

        logger.info("Retrieved workspace details for %s by user %s", workspace_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to get workspace details for %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to retrieve workspace details: {str(e)}")


@authenticated_tool(
    name="update_workspace",
    description="Update workspace information and settings",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_admin",
)
async def update_workspace(
    workspace_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update workspace information and settings. Requires admin role in the workspace.

    Args:
        workspace_id: The ID of the workspace to update
        name: New workspace name (optional)
        description: New workspace description (optional)
        settings: Additional settings to update (optional)

    Returns:
        Dictionary containing the updated workspace information

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
        MCPValidationError: If update fails
    """
    user_context = get_mcp_user_context()

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)

    try:
        # Validate input
        if name is not None:
            if len(name.strip()) < 3:
                raise MCPValidationError("Workspace name must be at least 3 characters long")
            if len(name.strip()) > 100:
                raise MCPValidationError("Workspace name cannot exceed 100 characters")

        # Prepare updates
        updates = {}
        if name is not None:
            updates["name"] = name.strip()
        if description is not None:
            updates["description"] = description.strip() if description else None
        if settings is not None:
            updates["settings"] = settings

        if not updates:
            raise MCPValidationError("No updates provided")

        # Update workspace using existing manager (validates admin permissions)
        result = await workspace_manager.update_workspace(
            workspace_id=workspace_id,
            admin_user_id=user_context.user_id,
            name=updates.get("name"),
            description=updates.get("description"),
            settings=updates.get("settings"),
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="update_workspace",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            changes=updates,
            metadata={"updated_fields": list(updates.keys())},
        )

        logger.info("Updated workspace %s by user %s", workspace_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to update workspace %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to update workspace: {str(e)}")


@authenticated_tool(
    name="delete_workspace",
    description="Delete a workspace and all associated resources",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_admin",
)
async def delete_workspace(workspace_id: str, confirm: bool = False) -> Dict[str, Any]:
    """
    Delete a workspace and clean up all associated resources. Requires owner role.

    Args:
        workspace_id: The ID of the workspace to delete
        confirm: Confirmation flag to prevent accidental deletion

    Returns:
        Dictionary containing deletion confirmation and cleanup details

    Raises:
        MCPAuthorizationError: If user is not the workspace owner
        MCPValidationError: If deletion fails or confirmation not provided
    """
    user_context = get_mcp_user_context()

    if not confirm:
        raise MCPValidationError("Workspace deletion requires explicit confirmation (confirm=true)")

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)

    try:
        # Get workspace info before deletion for audit
        workspace = await workspace_manager.get_workspace_by_id(workspace_id, user_context.user_id)

        # Delete workspace using existing manager (validates owner permissions)
        success = await workspace_manager.delete_workspace(workspace_id, user_context.user_id)

        if not success:
            raise MCPValidationError("Failed to delete workspace")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="delete_workspace",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            changes={"deleted": True},
            metadata={
                "workspace_name": workspace.get("name"),
                "member_count": len(workspace.get("members", [])),
                "sbd_account": workspace.get("sbd_account", {}).get("account_username"),
            },
        )

        logger.info("Deleted workspace %s by user %s", workspace_id, user_context.user_id)
        return {
            "workspace_id": workspace_id,
            "deleted": True,
            "deleted_at": datetime.now(),
            "deleted_by": user_context.user_id,
        }

    except Exception as e:
        logger.error("Failed to delete workspace %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to delete workspace: {str(e)}")


@authenticated_tool(
    name="get_workspace_settings",
    description="Get workspace configuration and settings",
    permissions=["workspace:read"],
    rate_limit_action="workspace_read",
)
async def get_workspace_settings(workspace_id: str) -> Dict[str, Any]:
    """
    Get comprehensive workspace configuration and settings.

    Args:
        workspace_id: The ID of the workspace

    Returns:
        Dictionary containing workspace settings and configuration

    Raises:
        MCPAuthorizationError: If user doesn't have access to the workspace
    """
    user_context = get_mcp_user_context()

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)

    try:
        # Get workspace details (validates membership)
        workspace = await workspace_manager.get_workspace_by_id(workspace_id, user_context.user_id)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_workspace_settings",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={"workspace_name": workspace.get("name")},
        )

        # Extract settings and configuration
        settings_info = workspace.get("settings", {})
        sbd_account = workspace.get("sbd_account", {})

        result = {
            "workspace_id": workspace_id,
            "name": workspace.get("name"),
            "description": workspace.get("description"),
            "settings": settings_info,
            "sbd_account_config": {
                "account_username": sbd_account.get("account_username"),
                "is_frozen": sbd_account.get("is_frozen", False),
                "notification_settings": sbd_account.get("notification_settings", {}),
            },
            "member_permissions": {
                "allow_member_invites": settings_info.get("allow_member_invites", True),
                "default_new_member_role": settings_info.get("default_new_member_role", "viewer"),
            },
            "backup_admins": settings_info.get("backup_admins", []),
            "created_at": workspace.get("created_at"),
            "updated_at": workspace.get("updated_at"),
        }

        logger.info("Retrieved workspace settings for %s by user %s", workspace_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to get workspace settings for %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to retrieve workspace settings: {str(e)}")


# Workspace Member Management Tools (Task 7.2)


class WorkspaceMemberAddRequest(BaseModel):
    """Request model for adding workspace member."""

    user_id: str = Field(..., description="User ID to add to workspace")
    role: str = Field("viewer", description="Role to assign (admin, editor, viewer)")


class WorkspaceMemberInviteRequest(BaseModel):
    """Request model for inviting workspace member."""

    email: str = Field(..., description="Email address of the user to invite")
    role: str = Field("viewer", description="Role to assign (admin, editor, viewer)")
    message: Optional[str] = Field(None, description="Personal invitation message")


@authenticated_tool(
    name="add_workspace_member",
    description="Add an existing user to the workspace",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_admin",
)
async def add_workspace_member(workspace_id: str, user_id: str, role: str = "viewer") -> Dict[str, Any]:
    """
    Add an existing user to the workspace with the specified role.

    Args:
        workspace_id: The ID of the workspace
        user_id: The ID of the user to add
        role: Role to assign (admin, editor, viewer)

    Returns:
        Dictionary containing member addition confirmation

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
        MCPValidationError: If member addition fails
    """
    user_context = get_mcp_user_context()

    # Validate role
    if role not in ["admin", "editor", "viewer"]:
        raise MCPValidationError("Role must be 'admin', 'editor', or 'viewer'")

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)

    try:
        # Add member using existing manager (validates admin permissions)
        result = await workspace_manager.add_member(
            workspace_id=workspace_id, admin_user_id=user_context.user_id, user_id_to_add=user_id, role=role
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="add_workspace_member",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            changes={"added_user_id": user_id, "role": role},
            metadata={"member_count": len(result.get("members", []))},
        )

        logger.info(
            "Added member %s to workspace %s with role %s by user %s", user_id, workspace_id, role, user_context.user_id
        )
        return {
            "workspace_id": workspace_id,
            "added_user_id": user_id,
            "role": role,
            "added_at": datetime.now(),
            "added_by": user_context.user_id,
        }

    except Exception as e:
        logger.error("Failed to add member %s to workspace %s: %s", user_id, workspace_id, e)
        raise MCPValidationError(f"Failed to add workspace member: {str(e)}")


@authenticated_tool(
    name="remove_workspace_member",
    description="Remove a member from the workspace",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_admin",
)
async def remove_workspace_member(workspace_id: str, member_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    """
    Remove a member from the workspace with proper authorization checks.

    Args:
        workspace_id: The ID of the workspace
        member_id: The ID of the member to remove
        reason: Optional reason for removal

    Returns:
        Dictionary containing removal confirmation and details

    Raises:
        MCPAuthorizationError: If user is not a workspace admin or trying to remove owner
        MCPValidationError: If removal fails
    """
    user_context = get_mcp_user_context()

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)

    try:
        # Get workspace info before removal for audit
        workspace = await workspace_manager.get_workspace_by_id(workspace_id, user_context.user_id)

        # Find member info for audit
        member_info = None
        for member in workspace.get("members", []):
            if member.get("user_id") == member_id:
                member_info = member
                break

        if not member_info:
            raise MCPValidationError("Member not found in workspace")

        # Remove member using existing manager (validates admin permissions and prevents owner removal)
        result = await workspace_manager.remove_member(
            workspace_id=workspace_id, admin_user_id=user_context.user_id, user_id_to_remove=member_id
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="remove_workspace_member",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            changes={"removed_member_id": member_id, "member_role": member_info.get("role"), "reason": reason},
            metadata={"member_count": len(result.get("members", []))},
        )

        logger.info("Removed member %s from workspace %s by user %s", member_id, workspace_id, user_context.user_id)
        return {
            "workspace_id": workspace_id,
            "removed_member_id": member_id,
            "removed_at": datetime.now(),
            "removed_by": user_context.user_id,
            "reason": reason,
        }

    except Exception as e:
        logger.error("Failed to remove member %s from workspace %s: %s", member_id, workspace_id, e)
        raise MCPValidationError(f"Failed to remove workspace member: {str(e)}")


@authenticated_tool(
    name="update_member_role",
    description="Update a workspace member's role",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_admin",
)
async def update_member_role(workspace_id: str, member_id: str, new_role: str) -> Dict[str, Any]:
    """
    Update a workspace member's role (admin operations).

    Args:
        workspace_id: The ID of the workspace
        member_id: The ID of the member to update
        new_role: New role to assign (admin, editor, viewer)

    Returns:
        Dictionary containing role update confirmation

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
        MCPValidationError: If role update fails
    """
    user_context = get_mcp_user_context()

    # Validate role
    if new_role not in ["admin", "editor", "viewer"]:
        raise MCPValidationError("Role must be 'admin', 'editor', or 'viewer'")

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)

    try:
        # Get current member info for audit
        workspace = await workspace_manager.get_workspace_by_id(workspace_id, user_context.user_id)

        member_info = None
        for member in workspace.get("members", []):
            if member.get("user_id") == member_id:
                member_info = member
                break

        if not member_info:
            raise MCPValidationError("Member not found in workspace")

        old_role = member_info.get("role")

        # Update member role using existing manager (validates admin permissions and prevents owner role change)
        result = await workspace_manager.update_member_role(
            workspace_id=workspace_id,
            admin_user_id=user_context.user_id,
            user_id_to_update=member_id,
            new_role=new_role,
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="update_member_role",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            changes={"member_id": member_id, "old_role": old_role, "new_role": new_role},
        )

        logger.info(
            "Updated role for member %s in workspace %s from %s to %s by user %s",
            member_id,
            workspace_id,
            old_role,
            new_role,
            user_context.user_id,
        )
        return {
            "workspace_id": workspace_id,
            "member_id": member_id,
            "old_role": old_role,
            "new_role": new_role,
            "updated_at": datetime.now(),
            "updated_by": user_context.user_id,
        }

    except Exception as e:
        logger.error("Failed to update member role for %s in workspace %s: %s", member_id, workspace_id, e)
        raise MCPValidationError(f"Failed to update member role: {str(e)}")


@authenticated_tool(
    name="get_workspace_members",
    description="Get all members of a workspace with their roles",
    permissions=["workspace:read"],
    rate_limit_action="workspace_read",
)
async def get_workspace_members(workspace_id: str) -> List[Dict[str, Any]]:
    """
    Get all members of a workspace including their roles and join dates.

    Args:
        workspace_id: The ID of the workspace

    Returns:
        List of workspace members with their information and roles

    Raises:
        MCPAuthorizationError: If user doesn't have access to the workspace
    """
    user_context = get_mcp_user_context()

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)

    try:
        # Get workspace details (validates membership)
        workspace = await workspace_manager.get_workspace_by_id(workspace_id, user_context.user_id)

        members = workspace.get("members", [])

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_workspace_members",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={"member_count": len(members)},
        )

        # Format response
        result = []
        for member in members:
            member_info = {
                "user_id": member.get("user_id"),
                "role": member.get("role"),
                "joined_at": member.get("joined_at"),
                "is_owner": member.get("user_id") == workspace.get("owner_id"),
            }
            result.append(member_info)

        logger.info(
            "Retrieved %d workspace members for workspace %s by user %s",
            len(result),
            workspace_id,
            user_context.user_id,
        )
        return result

    except Exception as e:
        logger.error("Failed to get workspace members for %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to retrieve workspace members: {str(e)}")


@authenticated_tool(
    name="invite_workspace_member",
    description="Send an invitation to join the workspace",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_invite",
)
async def invite_workspace_member(
    workspace_id: str, email: str, role: str = "viewer", message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send an invitation to join the workspace via email.

    Args:
        workspace_id: The ID of the workspace
        email: Email address of the user to invite
        role: Role to assign (admin, editor, viewer)
        message: Personal invitation message

    Returns:
        Dictionary containing invitation details and status

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
        MCPValidationError: If invitation fails
    """
    user_context = get_mcp_user_context()

    # Validate role
    if role not in ["admin", "editor", "viewer"]:
        raise MCPValidationError("Role must be 'admin', 'editor', or 'viewer'")

    # Validate email format (basic validation)
    if not email or "@" not in email:
        raise MCPValidationError("Valid email address is required")

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)

    try:
        # Get workspace details to validate admin access
        workspace = await workspace_manager.get_workspace_by_id(workspace_id, user_context.user_id)

        # Check if user is admin
        user_role = workspace_manager.get_user_role(user_context.user_id, workspace)
        if user_role != "admin":
            raise MCPAuthorizationError("Only workspace admins can send invitations")

        # For now, we'll create a placeholder invitation system
        # In a full implementation, this would integrate with an email service
        invitation_id = f"inv_{workspace_id}_{hash(email)}_{int(datetime.now().timestamp())}"

        # Create audit trail
        await create_mcp_audit_trail(
            operation="invite_workspace_member",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            changes={"invited_email": email, "role": role, "message": message},
            metadata={"invitation_id": invitation_id},
        )

        logger.info(
            "Sent workspace invitation for %s to workspace %s by user %s", email, workspace_id, user_context.user_id
        )

        return {
            "workspace_id": workspace_id,
            "invitation_id": invitation_id,
            "invited_email": email,
            "role": role,
            "message": message,
            "invited_by": user_context.user_id,
            "invited_at": datetime.now(),
            "status": "sent",
        }

    except Exception as e:
        logger.error("Failed to invite member %s to workspace %s: %s", email, workspace_id, e)
        raise MCPValidationError(f"Failed to send workspace invitation: {str(e)}")


@authenticated_tool(
    name="get_workspace_invitations",
    description="Get pending invitations for the workspace",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_read",
)
async def get_workspace_invitations(workspace_id: str) -> List[Dict[str, Any]]:
    """
    Get all pending invitations for the workspace.

    Args:
        workspace_id: The ID of the workspace

    Returns:
        List of pending invitations with details

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
    """
    user_context = get_mcp_user_context()

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)

    try:
        # Get workspace details to validate admin access
        workspace = await workspace_manager.get_workspace_by_id(workspace_id, user_context.user_id)

        # Check if user is admin
        user_role = workspace_manager.get_user_role(user_context.user_id, workspace)
        if user_role != "admin":
            raise MCPAuthorizationError("Only workspace admins can view invitations")

        # For now, return empty list as invitation system would need to be implemented
        # In a full implementation, this would query an invitations collection
        invitations = []

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_workspace_invitations",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={"invitation_count": len(invitations)},
        )

        logger.info(
            "Retrieved %d workspace invitations for workspace %s by user %s",
            len(invitations),
            workspace_id,
            user_context.user_id,
        )
        return invitations

    except Exception as e:
        logger.error("Failed to get workspace invitations for %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to retrieve workspace invitations: {str(e)}")


# Workspace Financial Management Tools (Task 7.3)


class TokenRequestCreate(BaseModel):
    """Request model for creating token request."""

    amount: int = Field(..., description="Amount of tokens to request", gt=0)
    reason: str = Field(..., description="Reason for the token request", min_length=5)


class TokenRequestReview(BaseModel):
    """Request model for reviewing token request."""

    action: str = Field(..., description="Action to take (approve or deny)")
    comments: Optional[str] = Field(None, description="Admin comments on the request")


class WalletPermissionsUpdate(BaseModel):
    """Request model for updating wallet permissions."""

    user_id: str = Field(..., description="User ID to update permissions for")
    can_spend: bool = Field(..., description="Whether user can spend tokens")
    spending_limit: int = Field(..., description="Spending limit (-1 for unlimited)")


@authenticated_tool(
    name="get_workspace_wallet",
    description="Get workspace SBD wallet information including balance and permissions",
    permissions=["workspace:read"],
    rate_limit_action="workspace_read",
)
async def get_workspace_wallet(workspace_id: str) -> Dict[str, Any]:
    """
    Get comprehensive workspace SBD wallet information including balance and user permissions.

    Args:
        workspace_id: The ID of the workspace

    Returns:
        Dictionary containing wallet information, balance, and permissions

    Raises:
        MCPAuthorizationError: If user doesn't have access to the workspace
        MCPValidationError: If wallet information retrieval fails
    """
    user_context = get_mcp_user_context()

    team_wallet_manager = TeamWalletManager(db_manager_instance=db_manager)

    try:
        # Get team wallet info using existing manager (validates membership)
        wallet_info = await team_wallet_manager.get_team_wallet_info(workspace_id, user_context.user_id)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_workspace_wallet",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={
                "account_username": wallet_info.get("account_username"),
                "balance": wallet_info.get("balance", 0),
            },
        )

        logger.info("Retrieved workspace wallet info for %s by user %s", workspace_id, user_context.user_id)
        return wallet_info

    except Exception as e:
        logger.error("Failed to get workspace wallet for %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to retrieve workspace wallet information: {str(e)}")


@authenticated_tool(
    name="create_workspace_token_request",
    description="Create a token request from the workspace SBD account",
    permissions=["workspace:member"],
    rate_limit_action="workspace_token_request",
)
async def create_workspace_token_request(workspace_id: str, amount: int, reason: str) -> Dict[str, Any]:
    """
    Create a token request from the workspace SBD account.

    Args:
        workspace_id: The ID of the workspace
        amount: Amount of tokens to request (must be positive)
        reason: Reason for the token request (minimum 5 characters)

    Returns:
        Dictionary containing token request details and status

    Raises:
        MCPAuthorizationError: If user doesn't have access to the workspace
        MCPValidationError: If request creation fails or validation errors
    """
    user_context = get_mcp_user_context()

    # Validate input
    if amount <= 0:
        raise MCPValidationError("Token amount must be positive")

    if not reason or len(reason.strip()) < 5:
        raise MCPValidationError("Reason must be at least 5 characters long")

    team_wallet_manager = TeamWalletManager(db_manager_instance=db_manager)

    try:
        # Create request context for audit
        request_context = {
            "user_id": user_context.user_id,
            "ip_address": user_context.ip_address,
            "user_agent": user_context.user_agent,
            "mcp_operation": True,
        }

        # Create token request using existing manager
        result = await team_wallet_manager.create_token_request(
            workspace_id=workspace_id,
            user_id=user_context.user_id,
            amount=amount,
            reason=reason.strip(),
            request_context=request_context,
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="create_workspace_token_request",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            changes={"amount": amount, "reason": reason, "request_id": result.get("request_id")},
            metadata={"auto_approved": result.get("auto_approved", False), "status": result.get("status")},
        )

        logger.info(
            "Created token request %s for workspace %s by user %s",
            result.get("request_id"),
            workspace_id,
            user_context.user_id,
        )
        return result

    except Exception as e:
        logger.error("Failed to create token request for workspace %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to create token request: {str(e)}")


@authenticated_tool(
    name="review_workspace_token_request",
    description="Review and approve/deny a workspace token request",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_admin",
)
async def review_workspace_token_request(
    request_id: str, action: str, comments: Optional[str] = None
) -> Dict[str, Any]:
    """
    Review a workspace token request by approving or denying it.

    Args:
        request_id: The ID of the token request to review
        action: Action to take ("approve" or "deny")
        comments: Optional admin comments on the request

    Returns:
        Dictionary containing review result and processing details

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
        MCPValidationError: If review fails or invalid action
    """
    user_context = get_mcp_user_context()

    # Validate action
    if action not in ["approve", "deny"]:
        raise MCPValidationError("Action must be 'approve' or 'deny'")

    team_wallet_manager = TeamWalletManager(db_manager_instance=db_manager)

    try:
        # Create request context for audit
        request_context = {
            "user_id": user_context.user_id,
            "ip_address": user_context.ip_address,
            "user_agent": user_context.user_agent,
            "mcp_operation": True,
        }

        # Review token request using existing manager (validates admin permissions)
        result = await team_wallet_manager.review_token_request(
            request_id=request_id,
            admin_id=user_context.user_id,
            action=action,
            comments=comments,
            request_context=request_context,
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="review_workspace_token_request",
            user_context=user_context,
            resource_type="token_request",
            resource_id=request_id,
            changes={"action": action, "comments": comments, "amount": result.get("amount")},
            metadata={"processed_at": result.get("processed_at"), "status": result.get("status")},
        )

        logger.info("Reviewed token request %s with action %s by user %s", request_id, action, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to review token request %s: %s", request_id, e)
        raise MCPValidationError(f"Failed to review token request: {str(e)}")


@authenticated_tool(
    name="get_workspace_token_requests",
    description="Get pending token requests for the workspace",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_read",
)
async def get_workspace_token_requests(workspace_id: str) -> List[Dict[str, Any]]:
    """
    Get all pending token requests for the workspace.

    Args:
        workspace_id: The ID of the workspace

    Returns:
        List of pending token requests with details

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
    """
    user_context = get_mcp_user_context()

    team_wallet_manager = TeamWalletManager(db_manager_instance=db_manager)

    try:
        # Get pending token requests using existing manager (validates admin permissions)
        requests = await team_wallet_manager.get_pending_token_requests(workspace_id, user_context.user_id)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_workspace_token_requests",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={"request_count": len(requests)},
        )

        logger.info(
            "Retrieved %d pending token requests for workspace %s by user %s",
            len(requests),
            workspace_id,
            user_context.user_id,
        )
        return requests

    except Exception as e:
        logger.error("Failed to get token requests for workspace %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to retrieve token requests: {str(e)}")


@authenticated_tool(
    name="update_wallet_permissions",
    description="Update spending permissions for a workspace member",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_admin",
)
async def update_wallet_permissions(
    workspace_id: str, user_id: str, can_spend: bool, spending_limit: int = 0
) -> Dict[str, Any]:
    """
    Update spending permissions for a workspace member.

    Args:
        workspace_id: The ID of the workspace
        user_id: The ID of the user to update permissions for
        can_spend: Whether the user can spend tokens
        spending_limit: Spending limit (-1 for unlimited, 0 for no spending)

    Returns:
        Dictionary containing permission update confirmation

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
        MCPValidationError: If permission update fails
    """
    user_context = get_mcp_user_context()

    # Validate spending limit
    if spending_limit < -1:
        raise MCPValidationError("Spending limit must be -1 (unlimited) or >= 0")

    team_wallet_manager = TeamWalletManager(db_manager_instance=db_manager)

    try:
        # Prepare permissions update
        permissions = {"can_spend": can_spend, "spending_limit": spending_limit}

        # Update spending permissions using existing manager (validates admin permissions)
        result = await team_wallet_manager.update_spending_permissions(
            workspace_id=workspace_id, admin_id=user_context.user_id, user_id=user_id, permissions=permissions
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="update_wallet_permissions",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            changes={"target_user_id": user_id, "can_spend": can_spend, "spending_limit": spending_limit},
        )

        logger.info(
            "Updated wallet permissions for user %s in workspace %s by user %s",
            user_id,
            workspace_id,
            user_context.user_id,
        )
        return result

    except Exception as e:
        logger.error("Failed to update wallet permissions for user %s in workspace %s: %s", user_id, workspace_id, e)
        raise MCPValidationError(f"Failed to update wallet permissions: {str(e)}")


@authenticated_tool(
    name="freeze_workspace_wallet",
    description="Freeze the workspace SBD account to prevent spending",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_admin",
)
async def freeze_workspace_wallet(workspace_id: str, reason: str) -> Dict[str, Any]:
    """
    Freeze the workspace SBD account to prevent all spending operations.

    Args:
        workspace_id: The ID of the workspace
        reason: Reason for freezing the account

    Returns:
        Dictionary containing freeze confirmation and details

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
        MCPValidationError: If freeze operation fails
    """
    user_context = get_mcp_user_context()

    # Validate reason
    if not reason or len(reason.strip()) < 5:
        raise MCPValidationError("Reason for freezing must be at least 5 characters long")

    team_wallet_manager = TeamWalletManager(db_manager_instance=db_manager)

    try:
        # Freeze team account using existing manager (validates admin permissions)
        result = await team_wallet_manager.freeze_team_account(
            workspace_id=workspace_id, admin_id=user_context.user_id, reason=reason.strip()
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="freeze_workspace_wallet",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            changes={"is_frozen": True, "reason": reason},
            metadata={"frozen_at": result.get("frozen_at")},
        )

        logger.info("Froze workspace wallet for %s by user %s", workspace_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to freeze workspace wallet for %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to freeze workspace wallet: {str(e)}")


@authenticated_tool(
    name="unfreeze_workspace_wallet",
    description="Unfreeze the workspace SBD account to allow spending",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_admin",
)
async def unfreeze_workspace_wallet(workspace_id: str) -> Dict[str, Any]:
    """
    Unfreeze the workspace SBD account to allow spending operations.

    Args:
        workspace_id: The ID of the workspace

    Returns:
        Dictionary containing unfreeze confirmation and details

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
        MCPValidationError: If unfreeze operation fails
    """
    user_context = get_mcp_user_context()

    team_wallet_manager = TeamWalletManager(db_manager_instance=db_manager)

    try:
        # Unfreeze team account using existing manager (validates admin permissions)
        result = await team_wallet_manager.unfreeze_team_account(
            workspace_id=workspace_id, admin_id=user_context.user_id
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="unfreeze_workspace_wallet",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            changes={"is_frozen": False},
            metadata={"unfrozen_at": result.get("unfrozen_at")},
        )

        logger.info("Unfroze workspace wallet for %s by user %s", workspace_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to unfreeze workspace wallet for %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to unfreeze workspace wallet: {str(e)}")


@authenticated_tool(
    name="get_workspace_transaction_history",
    description="Get transaction history for the workspace SBD account",
    permissions=["workspace:read"],
    rate_limit_action="workspace_read",
)
async def get_workspace_transaction_history(workspace_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get transaction history for the workspace SBD account.

    Args:
        workspace_id: The ID of the workspace
        limit: Maximum number of transactions to return (default 50, max 100)

    Returns:
        List of transactions with details and timestamps

    Raises:
        MCPAuthorizationError: If user doesn't have access to the workspace
        MCPValidationError: If transaction history retrieval fails
    """
    user_context = get_mcp_user_context()

    # Validate limit
    if limit <= 0 or limit > 100:
        raise MCPValidationError("Limit must be between 1 and 100")

    team_wallet_manager = TeamWalletManager(db_manager_instance=db_manager)

    try:
        # Get wallet info first to validate access
        wallet_info = await team_wallet_manager.get_team_wallet_info(workspace_id, user_context.user_id)

        # Get recent transactions (this would be part of wallet_info or a separate method)
        transactions = wallet_info.get("recent_transactions", [])

        # Limit the results
        limited_transactions = transactions[:limit]

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_workspace_transaction_history",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={"transaction_count": len(limited_transactions), "limit": limit},
        )

        logger.info(
            "Retrieved %d transactions for workspace %s by user %s",
            len(limited_transactions),
            workspace_id,
            user_context.user_id,
        )
        return limited_transactions

    except Exception as e:
        logger.error("Failed to get transaction history for workspace %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to retrieve transaction history: {str(e)}")


# Workspace Audit and Admin Tools (Task 7.4)


class BackupAdminRequest(BaseModel):
    """Request model for backup admin operations."""

    backup_admin_id: str = Field(..., description="User ID to designate as backup admin")


class EmergencyAccessRequest(BaseModel):
    """Request model for emergency access operations."""

    emergency_reason: str = Field(..., description="Reason for emergency access", min_length=10)


@authenticated_tool(
    name="get_workspace_audit_log",
    description="Get audit trail for workspace operations and compliance reporting",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_read",
)
async def get_workspace_audit_log(
    workspace_id: str, limit: int = 100, start_date: Optional[str] = None, end_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get comprehensive audit trail for workspace operations and compliance reporting.

    Args:
        workspace_id: The ID of the workspace
        limit: Maximum number of audit entries to return (default 100, max 500)
        start_date: Start date for audit log filtering (ISO format)
        end_date: End date for audit log filtering (ISO format)

    Returns:
        List of audit log entries with operation details and timestamps

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
        MCPValidationError: If audit log retrieval fails
    """
    user_context = get_mcp_user_context()

    # Validate limit
    if limit <= 0 or limit > 500:
        raise MCPValidationError("Limit must be between 1 and 500")

    team_wallet_manager = TeamWalletManager(db_manager_instance=db_manager)

    try:
        # Parse dates if provided
        parsed_start_date = None
        parsed_end_date = None

        if start_date:
            try:
                parsed_start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            except ValueError:
                raise MCPValidationError("Invalid start_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")

        if end_date:
            try:
                parsed_end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            except ValueError:
                raise MCPValidationError("Invalid end_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")

        # Get audit trail using existing manager (validates admin permissions)
        audit_entries = await team_wallet_manager.get_team_audit_trail(
            workspace_id=workspace_id,
            admin_id=user_context.user_id,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            limit=limit,
        )

        # Create audit trail for this operation
        await create_mcp_audit_trail(
            operation="get_workspace_audit_log",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={
                "audit_entry_count": len(audit_entries),
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
            },
        )

        logger.info(
            "Retrieved %d audit entries for workspace %s by user %s",
            len(audit_entries),
            workspace_id,
            user_context.user_id,
        )
        return audit_entries

    except Exception as e:
        logger.error("Failed to get audit log for workspace %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to retrieve audit log: {str(e)}")


@authenticated_tool(
    name="designate_backup_admin",
    description="Designate a backup admin for emergency workspace recovery",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_admin",
)
async def designate_backup_admin(workspace_id: str, backup_admin_id: str) -> Dict[str, Any]:
    """
    Designate a backup admin for emergency recovery operations.

    Args:
        workspace_id: The ID of the workspace
        backup_admin_id: The ID of the user to designate as backup admin

    Returns:
        Dictionary containing backup admin designation confirmation

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
        MCPValidationError: If backup admin designation fails
    """
    user_context = get_mcp_user_context()

    team_wallet_manager = TeamWalletManager(db_manager_instance=db_manager)

    try:
        # Designate backup admin using existing manager (validates admin permissions)
        result = await team_wallet_manager.designate_backup_admin(
            workspace_id=workspace_id, admin_id=user_context.user_id, backup_admin_id=backup_admin_id
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="designate_backup_admin",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            changes={"backup_admin_id": backup_admin_id},
            metadata={"designated_at": result.get("designated_at")},
        )

        logger.info(
            "Designated backup admin %s for workspace %s by user %s",
            backup_admin_id,
            workspace_id,
            user_context.user_id,
        )
        return result

    except Exception as e:
        logger.error("Failed to designate backup admin for workspace %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to designate backup admin: {str(e)}")


@authenticated_tool(
    name="remove_backup_admin",
    description="Remove a backup admin designation from the workspace",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_admin",
)
async def remove_backup_admin(workspace_id: str, backup_admin_id: str) -> Dict[str, Any]:
    """
    Remove a backup admin designation from the workspace.

    Args:
        workspace_id: The ID of the workspace
        backup_admin_id: The ID of the backup admin to remove

    Returns:
        Dictionary containing backup admin removal confirmation

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
        MCPValidationError: If backup admin removal fails
    """
    user_context = get_mcp_user_context()

    team_wallet_manager = TeamWalletManager(db_manager_instance=db_manager)

    try:
        # Remove backup admin using existing manager (validates admin permissions)
        result = await team_wallet_manager.remove_backup_admin(
            workspace_id=workspace_id, admin_id=user_context.user_id, backup_admin_id=backup_admin_id
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="remove_backup_admin",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            changes={"removed_backup_admin_id": backup_admin_id},
            metadata={"removed_at": result.get("removed_at")},
        )

        logger.info(
            "Removed backup admin %s from workspace %s by user %s", backup_admin_id, workspace_id, user_context.user_id
        )
        return result

    except Exception as e:
        logger.error("Failed to remove backup admin from workspace %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to remove backup admin: {str(e)}")


@authenticated_tool(
    name="emergency_workspace_access",
    description="Emergency unfreeze mechanism for backup admins when primary admins are unavailable",
    permissions=["workspace:backup_admin"],
    rate_limit_action="workspace_emergency",
)
async def emergency_workspace_access(workspace_id: str, emergency_reason: str) -> Dict[str, Any]:
    """
    Emergency unfreeze mechanism for backup admins when primary admins are unavailable.

    Args:
        workspace_id: The ID of the workspace
        emergency_reason: Detailed reason for emergency access (minimum 10 characters)

    Returns:
        Dictionary containing emergency access confirmation and details

    Raises:
        MCPAuthorizationError: If user is not a designated backup admin
        MCPValidationError: If emergency access fails
    """
    user_context = get_mcp_user_context()

    # Validate emergency reason
    if not emergency_reason or len(emergency_reason.strip()) < 10:
        raise MCPValidationError("Emergency reason must be at least 10 characters long")

    team_wallet_manager = TeamWalletManager(db_manager_instance=db_manager)

    try:
        # Perform emergency unfreeze using existing manager (validates backup admin permissions)
        result = await team_wallet_manager.emergency_unfreeze_account(
            workspace_id=workspace_id, backup_admin_id=user_context.user_id, emergency_reason=emergency_reason.strip()
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="emergency_workspace_access",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            changes={"emergency_unfrozen": True, "emergency_reason": emergency_reason},
            metadata={"unfrozen_at": result.get("unfrozen_at"), "emergency": True},
        )

        logger.warning("EMERGENCY ACCESS: Workspace %s unfrozen by backup admin %s", workspace_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed emergency workspace access for %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed emergency workspace access: {str(e)}")


@authenticated_tool(
    name="get_workspace_analytics",
    description="Get usage statistics and analytics for the workspace",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_read",
)
async def get_workspace_analytics(workspace_id: str) -> Dict[str, Any]:
    """
    Get comprehensive usage statistics and analytics for the workspace.

    Args:
        workspace_id: The ID of the workspace

    Returns:
        Dictionary containing workspace analytics and usage statistics

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
    """
    user_context = get_mcp_user_context()

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)
    team_wallet_manager = TeamWalletManager(db_manager_instance=db_manager)

    try:
        # Get workspace details (validates admin access)
        workspace = await workspace_manager.get_workspace_by_id(workspace_id, user_context.user_id)

        # Check if user is admin
        user_role = workspace_manager.get_user_role(user_context.user_id, workspace)
        if user_role != "admin":
            raise MCPAuthorizationError("Only workspace admins can view analytics")

        # Get wallet information for financial analytics
        try:
            wallet_info = await team_wallet_manager.get_team_wallet_info(workspace_id, user_context.user_id)
        except Exception:
            wallet_info = {}

        # Calculate analytics
        members = workspace.get("members", [])
        member_count = len(members)
        admin_count = len([m for m in members if m.get("role") == "admin"])

        # Basic analytics (in a full implementation, this would query activity logs)
        analytics = {
            "workspace_id": workspace_id,
            "workspace_name": workspace.get("name"),
            "created_at": workspace.get("created_at"),
            "member_statistics": {
                "total_members": member_count,
                "admin_count": admin_count,
                "editor_count": len([m for m in members if m.get("role") == "editor"]),
                "viewer_count": len([m for m in members if m.get("role") == "viewer"]),
            },
            "financial_statistics": {
                "sbd_account_username": wallet_info.get("account_username"),
                "current_balance": wallet_info.get("balance", 0),
                "is_frozen": wallet_info.get("is_frozen", False),
                "recent_transaction_count": len(wallet_info.get("recent_transactions", [])),
            },
            "settings": {
                "allow_member_invites": workspace.get("settings", {}).get("allow_member_invites", True),
                "default_new_member_role": workspace.get("settings", {}).get("default_new_member_role", "viewer"),
                "backup_admin_count": len(workspace.get("settings", {}).get("backup_admins", [])),
            },
            "last_updated": workspace.get("updated_at"),
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_workspace_analytics",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={"member_count": member_count},
        )

        logger.info("Retrieved workspace analytics for %s by user %s", workspace_id, user_context.user_id)
        return analytics

    except Exception as e:
        logger.error("Failed to get workspace analytics for %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to retrieve workspace analytics: {str(e)}")


@authenticated_tool(
    name="validate_workspace_access",
    description="Validate user permissions and access levels for the workspace",
    permissions=["workspace:read"],
    rate_limit_action="workspace_read",
)
async def validate_workspace_access(workspace_id: str) -> Dict[str, Any]:
    """
    Validate user permissions and access levels for the workspace.

    Args:
        workspace_id: The ID of the workspace

    Returns:
        Dictionary containing user access validation and permission details

    Raises:
        MCPAuthorizationError: If user doesn't have access to the workspace
    """
    user_context = get_mcp_user_context()

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)

    try:
        # Get workspace details (validates membership)
        workspace = await workspace_manager.get_workspace_by_id(workspace_id, user_context.user_id)

        # Get user's role and permissions
        user_role = workspace_manager.get_user_role(user_context.user_id, workspace)
        is_owner = workspace.get("owner_id") == user_context.user_id

        # Check backup admin status
        backup_admins = workspace.get("settings", {}).get("backup_admins", [])
        is_backup_admin = user_context.user_id in backup_admins

        # Get SBD account permissions if available
        sbd_permissions = {}
        sbd_account = workspace.get("sbd_account", {})
        if sbd_account.get("spending_permissions"):
            user_sbd_perms = sbd_account["spending_permissions"].get(user_context.user_id, {})
            sbd_permissions = {
                "can_spend": user_sbd_perms.get("can_spend", False),
                "spending_limit": user_sbd_perms.get("spending_limit", 0),
            }

        # Determine capabilities based on role
        capabilities = {
            "can_read": True,  # All members can read
            "can_edit": user_role in ["admin", "editor"],
            "can_admin": user_role == "admin" or is_owner,
            "can_delete": is_owner,
            "can_manage_members": user_role == "admin" or is_owner,
            "can_manage_wallet": user_role == "admin" or is_owner,
            "can_emergency_access": is_backup_admin,
            "can_view_audit": user_role == "admin" or is_owner,
        }

        access_validation = {
            "workspace_id": workspace_id,
            "user_id": user_context.user_id,
            "access_granted": True,
            "user_role": user_role,
            "is_owner": is_owner,
            "is_backup_admin": is_backup_admin,
            "capabilities": capabilities,
            "sbd_permissions": sbd_permissions,
            "workspace_status": {
                "is_frozen": sbd_account.get("is_frozen", False),
                "member_count": len(workspace.get("members", [])),
                "created_at": workspace.get("created_at"),
            },
            "validated_at": datetime.now(),
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="validate_workspace_access",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={"user_role": user_role, "is_owner": is_owner, "is_backup_admin": is_backup_admin},
        )

        logger.info("Validated workspace access for user %s in workspace %s", user_context.user_id, workspace_id)
        return access_validation

    except Exception as e:
        logger.error("Failed to validate workspace access for %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to validate workspace access: {str(e)}")


@authenticated_tool(
    name="get_workspace_health",
    description="Get workspace system status and health information",
    permissions=["workspace:admin"],
    rate_limit_action="workspace_read",
)
async def get_workspace_health(workspace_id: str) -> Dict[str, Any]:
    """
    Get comprehensive workspace system status and health information.

    Args:
        workspace_id: The ID of the workspace

    Returns:
        Dictionary containing workspace health status and system information

    Raises:
        MCPAuthorizationError: If user is not a workspace admin
    """
    user_context = get_mcp_user_context()

    workspace_manager = WorkspaceManager(db_manager_instance=db_manager)
    team_wallet_manager = TeamWalletManager(db_manager_instance=db_manager)

    try:
        # Get workspace details (validates admin access)
        workspace = await workspace_manager.get_workspace_by_id(workspace_id, user_context.user_id)

        # Check if user is admin
        user_role = workspace_manager.get_user_role(user_context.user_id, workspace)
        if user_role != "admin":
            raise MCPAuthorizationError("Only workspace admins can view health status")

        # Check wallet health
        wallet_health = {"status": "unknown", "issues": []}
        try:
            wallet_info = await team_wallet_manager.get_team_wallet_info(workspace_id, user_context.user_id)
            wallet_health["status"] = "healthy"

            if wallet_info.get("is_frozen"):
                wallet_health["issues"].append("Account is frozen")
                wallet_health["status"] = "warning"

            if not wallet_info.get("account_username"):
                wallet_health["issues"].append("SBD account not initialized")
                wallet_health["status"] = "warning"

        except Exception as e:
            wallet_health["status"] = "error"
            wallet_health["issues"].append(f"Wallet access error: {str(e)}")

        # Check member health
        members = workspace.get("members", [])
        member_health = {"status": "healthy", "issues": []}

        admin_count = len([m for m in members if m.get("role") == "admin"])
        if admin_count == 0:
            member_health["status"] = "critical"
            member_health["issues"].append("No admin members found")
        elif admin_count == 1:
            member_health["status"] = "warning"
            member_health["issues"].append("Only one admin member")

        # Overall health assessment
        overall_status = "healthy"
        if wallet_health["status"] == "error" or member_health["status"] == "critical":
            overall_status = "critical"
        elif wallet_health["status"] == "warning" or member_health["status"] == "warning":
            overall_status = "warning"

        health_report = {
            "workspace_id": workspace_id,
            "overall_status": overall_status,
            "checked_at": datetime.now(),
            "components": {
                "workspace": {
                    "status": "healthy",
                    "created_at": workspace.get("created_at"),
                    "last_updated": workspace.get("updated_at"),
                    "member_count": len(members),
                },
                "wallet": wallet_health,
                "members": member_health,
            },
            "backup_admins": len(workspace.get("settings", {}).get("backup_admins", [])),
            "recommendations": [],
        }

        # Add recommendations based on issues
        if admin_count <= 1:
            health_report["recommendations"].append("Consider adding more admin members for redundancy")

        if not wallet_info.get("account_username"):
            health_report["recommendations"].append("Initialize SBD wallet for financial operations")

        if len(workspace.get("settings", {}).get("backup_admins", [])) == 0:
            health_report["recommendations"].append("Designate backup admins for emergency recovery")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_workspace_health",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={"overall_status": overall_status, "component_count": len(health_report["components"])},
        )

        logger.info(
            "Retrieved workspace health for %s by user %s (status: %s)",
            workspace_id,
            user_context.user_id,
            overall_status,
        )
        return health_report

    except Exception as e:
        logger.error("Failed to get workspace health for %s: %s", workspace_id, e)
        raise MCPValidationError(f"Failed to retrieve workspace health: {str(e)}")
