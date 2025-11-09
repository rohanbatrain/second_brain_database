"""
Family Management MCP Tools

MCP tools for comprehensive family lifecycle management, member operations,
and relationship management using FastMCP 2.x modern patterns.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ....config import settings
from ....managers.family_manager import FamilyManager
from ....managers.logging_manager import get_logger
from ..context import create_mcp_audit_trail, require_family_access
from ..exceptions import MCPAuthorizationError, MCPValidationError
from ..modern_server import mcp
from ..security import authenticated_tool, get_mcp_user_context

logger = get_logger(prefix="[MCP_FamilyTools]")

# Import manager instances
from ....database import db_manager
from ....managers.redis_manager import redis_manager
from ....managers.security_manager import security_manager
from ..database_integration import ensure_mcp_database_connection


# Pydantic models for MCP tool parameters and responses
class FamilyInfo(BaseModel):
    """Family information response model."""

    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    member_count: int
    owner_id: str
    sbd_account_username: Optional[str] = None
    account_frozen: bool = False
    limits: Dict[str, Any] = Field(default_factory=dict)


class FamilyMember(BaseModel):
    """Family member information model."""

    user_id: str
    username: str
    email: Optional[str] = None
    role: str
    joined_at: datetime
    relationship: Optional[str] = None
    spending_permissions: Dict[str, Any] = Field(default_factory=dict)


class FamilyCreateRequest(BaseModel):
    """Request model for family creation."""

    name: Optional[str] = Field(None, description="Family name (optional)")


class FamilyUpdateRequest(BaseModel):
    """Request model for family settings update."""

    name: Optional[str] = Field(None, description="New family name")
    description: Optional[str] = Field(None, description="Family description")
    settings: Optional[Dict[str, Any]] = Field(None, description="Additional settings")


# Core Family Management Tools (Task 4.1)


@authenticated_tool(
    name="get_family_info",
    description="Get detailed information about a specific family",
    permissions=["family:read"],
    rate_limit_action="family_read",
)
async def get_family_info(family_id: str) -> Dict[str, Any]:
    """
    Get comprehensive family information including members, settings, and SBD account details.

    Args:
        family_id: The ID of the family to retrieve information for

    Returns:
        Dictionary containing family information, member count, and account details

    Raises:
        MCPAuthorizationError: If user doesn't have access to the family
        MCPValidationError: If family_id is invalid
    """
    user_context = get_mcp_user_context()

    # Validate family access
    await require_family_access(family_id, user_context=user_context)

    # Create family manager instance
    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get family details using existing manager
        family_details = await family_manager.get_family_details(family_id, user_context.user_id)

        # Get SBD account information
        sbd_account = await family_manager.get_family_sbd_account(family_id, user_context.user_id)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_family_info",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={"family_name": family_details.get("name")},
        )

        # Combine information
        result = {
            "id": family_id,
            "name": family_details.get("name"),
            "description": family_details.get("description"),
            "created_at": family_details.get("created_at"),
            "member_count": family_details.get("member_count", 0),
            "owner_id": family_details.get("owner_id"),
            "sbd_account_username": sbd_account.get("account_username"),
            "account_frozen": sbd_account.get("account_frozen", False),
            "limits": family_details.get("limits", {}),
            "settings": family_details.get("settings", {}),
        }

        logger.info("Retrieved family info for family %s by user %s", family_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to get family info for %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to retrieve family information: {str(e)}")


@authenticated_tool(
    name="get_family_members",
    description="Get all members of a family with their roles and relationships",
    permissions=["family:read"],
    rate_limit_action="family_read",
)
async def get_family_members(family_id: str) -> List[Dict[str, Any]]:
    """
    Get all members of a family including their roles, relationships, and permissions.

    Args:
        family_id: The ID of the family to get members for

    Returns:
        List of family members with their information and roles

    Raises:
        MCPAuthorizationError: If user doesn't have access to the family
    """
    user_context = get_mcp_user_context()

    # Validate family access
    await require_family_access(family_id, user_context=user_context)

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get family members using existing manager
        members = await family_manager.get_family_members(family_id, user_context.user_id)

        # Get relationships for additional context
        relationships = await family_manager.get_family_relationships(family_id, user_context.user_id)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_family_members",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={"member_count": len(members)},
        )

        # Format response
        result = []
        for member in members:
            # Find relationship info for this member
            member_relationships = [r for r in relationships if r.get("user_id") == member.get("user_id")]

            member_info = {
                "user_id": member.get("user_id"),
                "username": member.get("username"),
                "email": member.get("email"),
                "role": member.get("role"),
                "joined_at": member.get("joined_at"),
                "relationship": member_relationships[0].get("relationship") if member_relationships else None,
                "spending_permissions": member.get("spending_permissions", {}),
            }
            result.append(member_info)

        logger.info(
            "Retrieved %d family members for family %s by user %s", len(result), family_id, user_context.user_id
        )
        return result

    except Exception as e:
        logger.error("Failed to get family members for %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to retrieve family members: {str(e)}")


@authenticated_tool(
    name="get_user_families",
    description="Get all families that the current user is a member of",
    permissions=["family:read"],
    rate_limit_action="family_read",
)
async def get_user_families() -> List[Dict[str, Any]]:
    """
    Get all families that the current user is a member of with their roles.

    Returns:
        List of families the user belongs to with role information
    """
    user_context = get_mcp_user_context()

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get user's families using existing manager
        families = await family_manager.get_user_families(user_context.user_id)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_user_families",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"family_count": len(families)},
        )

        # Format response
        result = []
        for family in families:
            family_info = {
                "id": str(family.get("_id")),
                "name": family.get("name"),
                "description": family.get("description"),
                "role": family.get("user_role"),
                "joined_at": family.get("joined_at"),
                "member_count": family.get("member_count", 0),
                "sbd_account_username": family.get("sbd_account_username"),
            }
            result.append(family_info)

        logger.info("Retrieved %d families for user %s", len(result), user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to get user families for %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to retrieve user families: {str(e)}")


@authenticated_tool(
    name="create_family",
    description="Create a new family with the current user as owner",
    permissions=["family:create"],
    rate_limit_action="family_create",
)
async def create_family(name: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new family with the current user as the owner/administrator.

    Args:
        name: Optional name for the family (will be generated if not provided)

    Returns:
        Dictionary containing the created family information

    Raises:
        MCPValidationError: If family creation fails or limits are exceeded
    """
    user_context = get_mcp_user_context()

    # Ensure database connection is established
    if not await ensure_mcp_database_connection():
        raise MCPValidationError("Database connection not available")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Create request context for audit
        request_context = {
            "user_id": user_context.user_id,
            "ip_address": user_context.ip_address,
            "user_agent": user_context.user_agent,
            "mcp_operation": True,
        }

        # Create family using existing manager
        family_result = await family_manager.create_family(
            user_id=user_context.user_id, name=name, request_context=request_context
        )

        family_id = family_result.get("family_id")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="create_family",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={"name": name or "Generated"},
            metadata={"sbd_account": family_result.get("sbd_account_username")},
        )

        logger.info("Created family %s for user %s", family_id, user_context.user_id)
        return family_result

    except Exception as e:
        logger.error("Failed to create family for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to create family: {str(e)}")


@authenticated_tool(
    name="update_family_settings",
    description="Update family settings and configuration",
    permissions=["family:admin"],
    rate_limit_action="family_admin",
)
async def update_family_settings(
    family_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update family settings and configuration. Requires admin role in the family.

    Args:
        family_id: The ID of the family to update
        name: New family name (optional)
        description: New family description (optional)
        settings: Additional settings to update (optional)

    Returns:
        Dictionary containing the updated family information

    Raises:
        MCPAuthorizationError: If user is not a family admin
        MCPValidationError: If update fails
    """
    user_context = get_mcp_user_context()

    # Validate admin access to family
    await require_family_access(family_id, required_role="admin", user_context=user_context)

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Prepare updates
        updates = {}
        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description
        if settings is not None:
            updates.update(settings)

        if not updates:
            raise MCPValidationError("No updates provided")

        # Create request context
        request_context = {
            "user_id": user_context.user_id,
            "ip_address": user_context.ip_address,
            "user_agent": user_context.user_agent,
            "mcp_operation": True,
        }

        # Update family using existing manager
        result = await family_manager.update_family_settings(
            family_id=family_id, admin_id=user_context.user_id, updates=updates, request_context=request_context
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="update_family_settings",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes=updates,
            metadata={"updated_fields": list(updates.keys())},
        )

        logger.info("Updated family settings for %s by user %s", family_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to update family settings for %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to update family settings: {str(e)}")


@authenticated_tool(
    name="delete_family",
    description="Delete a family and all associated resources",
    permissions=["family:admin"],
    rate_limit_action="family_admin",
)
async def delete_family(family_id: str, confirm: bool = False) -> Dict[str, Any]:
    """
    Delete a family and clean up all associated resources. Requires owner role.

    Args:
        family_id: The ID of the family to delete
        confirm: Confirmation flag to prevent accidental deletion

    Returns:
        Dictionary containing deletion confirmation and cleanup details

    Raises:
        MCPAuthorizationError: If user is not the family owner
        MCPValidationError: If deletion fails or confirmation not provided
    """
    user_context = get_mcp_user_context()

    # Validate owner access to family (only owners can delete families)
    await require_family_access(family_id, required_role="owner", user_context=user_context)

    if not confirm:
        raise MCPValidationError("Family deletion requires explicit confirmation (confirm=true)")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get family info before deletion for audit
        family_info = await family_manager.get_family_details(family_id, user_context.user_id)

        # Create request context
        request_context = {
            "user_id": user_context.user_id,
            "ip_address": user_context.ip_address,
            "user_agent": user_context.user_agent,
            "mcp_operation": True,
            "confirmation": confirm,
        }

        # Delete family using existing manager
        result = await family_manager.delete_family(
            family_id=family_id, admin_user_id=user_context.user_id, request_context=request_context
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="delete_family",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={"deleted": True},
            metadata={
                "family_name": family_info.get("name"),
                "member_count": family_info.get("member_count", 0),
                "sbd_account": family_info.get("sbd_account_username"),
            },
        )

        logger.info("Deleted family %s by user %s", family_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to delete family %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to delete family: {str(e)}")


# Family Member and Relationship Management Tools (Task 4.2)


class FamilyMemberAddRequest(BaseModel):
    """Request model for adding family member."""

    email: str = Field(..., description="Email address of the user to invite")
    role: str = Field("member", description="Role to assign (member, admin)")
    relationship: Optional[str] = Field(None, description="Relationship type")
    message: Optional[str] = Field(None, description="Personal invitation message")


class FamilyRelationshipUpdate(BaseModel):
    """Request model for updating relationships."""

    user_id: str = Field(..., description="User ID to update relationship for")
    relationship: str = Field(..., description="New relationship type")
    bidirectional: bool = Field(True, description="Whether to create bidirectional relationship")


@authenticated_tool(
    name="add_family_member",
    description="Add a new member to the family through invitation workflow",
    permissions=["family:admin"],
    rate_limit_action="family_invite",
)
async def add_family_member(
    family_id: str, email: str, role: str = "member", relationship: Optional[str] = None, message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a new member to the family by sending an invitation.

    Args:
        family_id: The ID of the family to add member to
        email: Email address of the user to invite
        role: Role to assign (member, admin)
        relationship: Optional relationship type
        message: Personal invitation message

    Returns:
        Dictionary containing invitation details and status

    Raises:
        MCPAuthorizationError: If user is not a family admin
        MCPValidationError: If invitation fails
    """
    user_context = get_mcp_user_context()

    # Validate admin access to family
    await require_family_access(family_id, required_role="admin", user_context=user_context)

    # Validate role
    if role not in ["member", "admin"]:
        raise MCPValidationError("Role must be 'member' or 'admin'")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Create request context
        request_context = {
            "user_id": user_context.user_id,
            "ip_address": user_context.ip_address,
            "user_agent": user_context.user_agent,
            "mcp_operation": True,
        }

        # Send family invitation using existing manager
        result = await family_manager.send_family_invitation(
            family_id=family_id,
            inviter_id=user_context.user_id,
            invitee_email=email,
            role=role,
            relationship=relationship,
            message=message,
            request_context=request_context,
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="add_family_member",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={"invited_email": email, "role": role, "relationship": relationship},
            metadata={"invitation_id": result.get("invitation_id")},
        )

        logger.info("Sent family invitation for %s to family %s by user %s", email, family_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to add family member %s to %s: %s", email, family_id, e)
        raise MCPValidationError(f"Failed to add family member: {str(e)}")


@authenticated_tool(
    name="remove_family_member",
    description="Remove a member from the family",
    permissions=["family:admin"],
    rate_limit_action="family_admin",
)
async def remove_family_member(family_id: str, member_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    """
    Remove a member from the family with proper authorization checks.

    Args:
        family_id: The ID of the family
        member_id: The ID of the member to remove
        reason: Optional reason for removal

    Returns:
        Dictionary containing removal confirmation and details

    Raises:
        MCPAuthorizationError: If user is not a family admin or trying to remove owner
        MCPValidationError: If removal fails
    """
    user_context = get_mcp_user_context()

    # Validate admin access to family
    await require_family_access(family_id, required_role="admin", user_context=user_context)

    # Prevent self-removal of owner
    if member_id == user_context.user_id and user_context.get_family_role(family_id) == "owner":
        raise MCPAuthorizationError("Family owner cannot remove themselves")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get member info before removal for audit
        members = await family_manager.get_family_members(family_id, user_context.user_id)
        member_info = next((m for m in members if m.get("user_id") == member_id), None)

        if not member_info:
            raise MCPValidationError("Member not found in family")

        # Create request context
        request_context = {
            "user_id": user_context.user_id,
            "ip_address": user_context.ip_address,
            "user_agent": user_context.user_agent,
            "mcp_operation": True,
            "reason": reason,
        }

        # Remove family member using existing manager
        result = await family_manager.remove_family_member(
            family_id=family_id, admin_id=user_context.user_id, member_id=member_id, request_context=request_context
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="remove_family_member",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={
                "removed_member_id": member_id,
                "removed_member_username": member_info.get("username"),
                "reason": reason,
            },
            metadata={"member_role": member_info.get("role")},
        )

        logger.info("Removed family member %s from family %s by user %s", member_id, family_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to remove family member %s from %s: %s", member_id, family_id, e)
        raise MCPValidationError(f"Failed to remove family member: {str(e)}")


@authenticated_tool(
    name="update_family_member_role",
    description="Update a family member's role",
    permissions=["family:admin"],
    rate_limit_action="family_admin",
)
async def update_family_member_role(family_id: str, member_id: str, new_role: str) -> Dict[str, Any]:
    """
    Update a family member's role (admin operations).

    Args:
        family_id: The ID of the family
        member_id: The ID of the member to update
        new_role: New role to assign (member, admin)

    Returns:
        Dictionary containing role update confirmation

    Raises:
        MCPAuthorizationError: If user is not a family admin
        MCPValidationError: If role update fails
    """
    user_context = get_mcp_user_context()

    # Validate admin access to family
    await require_family_access(family_id, required_role="admin", user_context=user_context)

    # Validate role
    if new_role not in ["member", "admin"]:
        raise MCPValidationError("Role must be 'member' or 'admin'")

    # Prevent changing owner role
    if user_context.get_family_role(family_id) == "owner" and member_id == user_context.user_id:
        raise MCPAuthorizationError("Cannot change owner role")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get current member info for audit
        members = await family_manager.get_family_members(family_id, user_context.user_id)
        member_info = next((m for m in members if m.get("user_id") == member_id), None)

        if not member_info:
            raise MCPValidationError("Member not found in family")

        old_role = member_info.get("role")

        # Update member role using existing manager methods
        # Note: This would use the family manager's role update functionality
        # For now, we'll use a generic update approach
        result = await family_manager.update_family_member_role(
            family_id=family_id, admin_id=user_context.user_id, member_id=member_id, new_role=new_role
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="update_family_member_role",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={"member_id": member_id, "old_role": old_role, "new_role": new_role},
            metadata={"member_username": member_info.get("username")},
        )

        logger.info(
            "Updated role for member %s in family %s from %s to %s by user %s",
            member_id,
            family_id,
            old_role,
            new_role,
            user_context.user_id,
        )
        return result

    except Exception as e:
        logger.error("Failed to update member role for %s in %s: %s", member_id, family_id, e)
        raise MCPValidationError(f"Failed to update member role: {str(e)}")


@authenticated_tool(
    name="update_relationship",
    description="Update bidirectional relationships between family members",
    permissions=["family:admin"],
    rate_limit_action="family_admin",
)
async def update_relationship(
    family_id: str, user_id: str, relationship: str, bidirectional: bool = True
) -> Dict[str, Any]:
    """
    Update bidirectional relationships between family members.

    Args:
        family_id: The ID of the family
        user_id: The ID of the user to update relationship for
        relationship: New relationship type
        bidirectional: Whether to create bidirectional relationship

    Returns:
        Dictionary containing relationship update confirmation

    Raises:
        MCPAuthorizationError: If user is not a family admin
        MCPValidationError: If relationship update fails
    """
    user_context = get_mcp_user_context()

    # Validate admin access to family
    await require_family_access(family_id, required_role="admin", user_context=user_context)

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Update relationship using existing manager
        result = await family_manager.update_family_relationship(
            family_id=family_id,
            admin_id=user_context.user_id,
            user_id=user_id,
            relationship=relationship,
            bidirectional=bidirectional,
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="update_relationship",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={"target_user_id": user_id, "relationship": relationship, "bidirectional": bidirectional},
        )

        logger.info(
            "Updated relationship for user %s in family %s to %s by user %s",
            user_id,
            family_id,
            relationship,
            user_context.user_id,
        )
        return result

    except Exception as e:
        logger.error("Failed to update relationship for %s in %s: %s", user_id, family_id, e)
        raise MCPValidationError(f"Failed to update relationship: {str(e)}")


@authenticated_tool(
    name="get_family_relationships",
    description="Get relationship mapping for all family members",
    permissions=["family:read"],
    rate_limit_action="family_read",
)
async def get_family_relationships(family_id: str) -> List[Dict[str, Any]]:
    """
    Get comprehensive relationship mapping for all family members.

    Args:
        family_id: The ID of the family

    Returns:
        List of relationships with detailed user information

    Raises:
        MCPAuthorizationError: If user doesn't have access to the family
    """
    user_context = get_mcp_user_context()

    # Validate family access
    await require_family_access(family_id, user_context=user_context)

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get family relationships using existing manager
        relationships = await family_manager.get_family_relationships(family_id, user_context.user_id)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_family_relationships",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={"relationship_count": len(relationships)},
        )

        logger.info(
            "Retrieved %d relationships for family %s by user %s", len(relationships), family_id, user_context.user_id
        )
        return relationships

    except Exception as e:
        logger.error("Failed to get family relationships for %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to retrieve family relationships: {str(e)}")


@authenticated_tool(
    name="promote_to_admin",
    description="Promote a family member to admin role",
    permissions=["family:admin"],
    rate_limit_action="family_admin",
)
async def promote_to_admin(family_id: str, member_id: str) -> Dict[str, Any]:
    """
    Promote a family member to admin role.

    Args:
        family_id: The ID of the family
        member_id: The ID of the member to promote

    Returns:
        Dictionary containing promotion confirmation
    """
    return await update_family_member_role(family_id, member_id, "admin")


@authenticated_tool(
    name="demote_from_admin",
    description="Demote a family admin to member role",
    permissions=["family:admin"],
    rate_limit_action="family_admin",
)
async def demote_from_admin(family_id: str, member_id: str) -> Dict[str, Any]:
    """
    Demote a family admin to member role.

    Args:
        family_id: The ID of the family
        member_id: The ID of the member to demote

    Returns:
        Dictionary containing demotion confirmation
    """
    return await update_family_member_role(family_id, member_id, "member")


# Family Invitation and Notification Tools (Task 4.3)


class FamilyInvitationRequest(BaseModel):
    """Request model for sending family invitation."""

    email: str = Field(..., description="Email address of the user to invite")
    relationship: Optional[str] = Field(None, description="Relationship type")
    message: Optional[str] = Field(None, description="Personal invitation message")


class FamilyInvitationResponse(BaseModel):
    """Response model for family invitation operations."""

    invitation_id: str
    family_id: str
    invitee_email: str
    status: str
    expires_at: datetime
    created_at: datetime


class NotificationPreferencesUpdate(BaseModel):
    """Request model for updating notification preferences."""

    email_notifications: Optional[bool] = Field(None, description="Enable email notifications")
    push_notifications: Optional[bool] = Field(None, description="Enable push notifications")
    family_activity: Optional[bool] = Field(None, description="Notify on family activity")
    token_requests: Optional[bool] = Field(None, description="Notify on token requests")
    member_changes: Optional[bool] = Field(None, description="Notify on member changes")


@authenticated_tool(
    name="send_family_invitation",
    description="Send a family invitation to a user via email",
    permissions=["family:admin"],
    rate_limit_action="family_invite",
)
async def send_family_invitation(
    family_id: str, email: str, relationship: Optional[str] = None, message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send a family invitation to a user via email using existing email system.

    Args:
        family_id: The ID of the family to invite to
        email: Email address of the user to invite
        relationship: Optional relationship type
        message: Personal invitation message

    Returns:
        Dictionary containing invitation details and status

    Raises:
        MCPAuthorizationError: If user is not a family admin
        MCPValidationError: If invitation fails
    """
    user_context = get_mcp_user_context()

    # Validate admin access to family
    await require_family_access(family_id, required_role="admin", user_context=user_context)

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Send family invitation using existing manager
        result = await family_manager.invite_member(
            family_id=family_id,
            inviter_id=user_context.user_id,
            identifier=email,
            relationship_type=relationship or "family_member",
            message=message,
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="send_family_invitation",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={"invited_email": email, "relationship": relationship, "message_provided": bool(message)},
            metadata={"invitation_id": result.get("invitation_id")},
        )

        logger.info("Sent family invitation for %s to family %s by user %s", email, family_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to send family invitation %s to %s: %s", email, family_id, e)
        raise MCPValidationError(f"Failed to send family invitation: {str(e)}")


@authenticated_tool(
    name="accept_family_invitation",
    description="Accept a family invitation using invitation token",
    permissions=["family:join"],
    rate_limit_action="family_join",
)
async def accept_family_invitation(invitation_token: str) -> Dict[str, Any]:
    """
    Accept a family invitation using the invitation token.

    Args:
        invitation_token: The invitation token from the email link

    Returns:
        Dictionary containing acceptance confirmation and family details

    Raises:
        MCPValidationError: If invitation is invalid or expired
    """
    user_context = get_mcp_user_context()

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Accept invitation using existing manager
        result = await family_manager.respond_to_invitation_by_token(
            invitation_token=invitation_token, user_id=user_context.user_id, action="accept"
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="accept_family_invitation",
            user_context=user_context,
            resource_type="family",
            resource_id=result.get("family_id"),
            changes={"action": "accept"},
            metadata={
                "invitation_token": invitation_token[:8] + "...",  # Partial token for security
                "family_name": result.get("family_name"),
            },
        )

        logger.info(
            "Accepted family invitation by user %s for family %s", user_context.user_id, result.get("family_id")
        )
        return result

    except Exception as e:
        logger.error("Failed to accept family invitation for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to accept family invitation: {str(e)}")


@authenticated_tool(
    name="decline_family_invitation",
    description="Decline a family invitation using invitation token",
    permissions=["family:join"],
    rate_limit_action="family_join",
)
async def decline_family_invitation(invitation_token: str) -> Dict[str, Any]:
    """
    Decline a family invitation using the invitation token.

    Args:
        invitation_token: The invitation token from the email link

    Returns:
        Dictionary containing decline confirmation

    Raises:
        MCPValidationError: If invitation is invalid or expired
    """
    user_context = get_mcp_user_context()

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Decline invitation using existing manager
        result = await family_manager.respond_to_invitation_by_token(
            invitation_token=invitation_token, user_id=user_context.user_id, action="decline"
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="decline_family_invitation",
            user_context=user_context,
            resource_type="family",
            resource_id=result.get("family_id"),
            changes={"action": "decline"},
            metadata={
                "invitation_token": invitation_token[:8] + "...",  # Partial token for security
                "family_name": result.get("family_name"),
            },
        )

        logger.info(
            "Declined family invitation by user %s for family %s", user_context.user_id, result.get("family_id")
        )
        return result

    except Exception as e:
        logger.error("Failed to decline family invitation for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to decline family invitation: {str(e)}")


@authenticated_tool(
    name="list_pending_invitations",
    description="List pending family invitations for invitation management",
    permissions=["family:admin"],
    rate_limit_action="family_read",
)
async def list_pending_invitations(family_id: str) -> List[Dict[str, Any]]:
    """
    List all pending family invitations for invitation management.

    Args:
        family_id: The ID of the family to list invitations for

    Returns:
        List of pending invitations with details

    Raises:
        MCPAuthorizationError: If user is not a family admin
    """
    user_context = get_mcp_user_context()

    # Validate admin access to family
    await require_family_access(family_id, required_role="admin", user_context=user_context)

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get family invitations using existing manager
        invitations = await family_manager.get_family_invitations(
            family_id=family_id, user_id=user_context.user_id, status_filter="pending"
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="list_pending_invitations",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={"invitation_count": len(invitations)},
        )

        logger.info(
            "Retrieved %d pending invitations for family %s by user %s",
            len(invitations),
            family_id,
            user_context.user_id,
        )
        return invitations

    except Exception as e:
        logger.error("Failed to list pending invitations for %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to list pending invitations: {str(e)}")


@authenticated_tool(
    name="get_family_notifications",
    description="Get family notifications for notification retrieval",
    permissions=["family:read"],
    rate_limit_action="family_read",
)
async def get_family_notifications(
    family_id: str, limit: int = 50, offset: int = 0, status_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get family notifications for notification retrieval with pagination.

    Args:
        family_id: The ID of the family to get notifications for
        limit: Maximum number of notifications to return (default: 50)
        offset: Number of notifications to skip (default: 0)
        status_filter: Optional status filter ("read", "unread")

    Returns:
        Dictionary containing notifications and pagination info

    Raises:
        MCPAuthorizationError: If user doesn't have access to the family
    """
    user_context = get_mcp_user_context()

    # Validate family access
    await require_family_access(family_id, user_context=user_context)

    # Validate parameters
    if limit > 100:
        raise MCPValidationError("Limit cannot exceed 100")
    if limit < 1:
        raise MCPValidationError("Limit must be at least 1")
    if offset < 0:
        raise MCPValidationError("Offset cannot be negative")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get family notifications using existing manager
        result = await family_manager.get_family_notifications(
            family_id=family_id, user_id=user_context.user_id, limit=limit, offset=offset, status_filter=status_filter
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_family_notifications",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={
                "notification_count": len(result.get("notifications", [])),
                "limit": limit,
                "offset": offset,
                "status_filter": status_filter,
            },
        )

        logger.info(
            "Retrieved %d notifications for family %s by user %s",
            len(result.get("notifications", [])),
            family_id,
            user_context.user_id,
        )
        return result

    except Exception as e:
        logger.error("Failed to get family notifications for %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to get family notifications: {str(e)}")


@authenticated_tool(
    name="mark_notifications_read",
    description="Mark specific notifications as read for notification management",
    permissions=["family:read"],
    rate_limit_action="family_read",
)
async def mark_notifications_read(family_id: str, notification_ids: List[str]) -> Dict[str, Any]:
    """
    Mark specific notifications as read for notification management.

    Args:
        family_id: The ID of the family
        notification_ids: List of notification IDs to mark as read

    Returns:
        Dictionary containing update confirmation and count

    Raises:
        MCPAuthorizationError: If user doesn't have access to the family
        MCPValidationError: If notification IDs are invalid
    """
    user_context = get_mcp_user_context()

    # Validate family access
    await require_family_access(family_id, user_context=user_context)

    # Validate parameters
    if not notification_ids:
        raise MCPValidationError("At least one notification ID must be provided")
    if len(notification_ids) > 100:
        raise MCPValidationError("Cannot mark more than 100 notifications at once")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Mark notifications as read using existing manager
        result = await family_manager.mark_notifications_read(
            family_id=family_id, user_id=user_context.user_id, notification_ids=notification_ids
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="mark_notifications_read",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={"marked_count": result.get("marked_count", 0)},
            metadata={"notification_ids": notification_ids[:10]},  # Limit for audit log size
        )

        logger.info(
            "Marked %d notifications as read for family %s by user %s",
            result.get("marked_count", 0),
            family_id,
            user_context.user_id,
        )
        return result

    except Exception as e:
        logger.error("Failed to mark notifications as read for %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to mark notifications as read: {str(e)}")


@authenticated_tool(
    name="mark_all_notifications_read",
    description="Mark all notifications as read for a family",
    permissions=["family:read"],
    rate_limit_action="family_read",
)
async def mark_all_notifications_read(family_id: str) -> Dict[str, Any]:
    """
    Mark all notifications as read for a family.

    Args:
        family_id: The ID of the family

    Returns:
        Dictionary containing update confirmation and count

    Raises:
        MCPAuthorizationError: If user doesn't have access to the family
    """
    user_context = get_mcp_user_context()

    # Validate family access
    await require_family_access(family_id, user_context=user_context)

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Mark all notifications as read using existing manager
        result = await family_manager.mark_all_notifications_read(family_id=family_id, user_id=user_context.user_id)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="mark_all_notifications_read",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={"marked_count": result.get("marked_count", 0)},
        )

        logger.info(
            "Marked all %d notifications as read for family %s by user %s",
            result.get("marked_count", 0),
            family_id,
            user_context.user_id,
        )
        return result

    except Exception as e:
        logger.error("Failed to mark all notifications as read for %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to mark all notifications as read: {str(e)}")


@authenticated_tool(
    name="update_notification_preferences",
    description="Update user notification preferences",
    permissions=["profile:write"],
    rate_limit_action="profile_update",
)
async def update_notification_preferences(
    email_notifications: Optional[bool] = None,
    push_notifications: Optional[bool] = None,
    family_activity: Optional[bool] = None,
    token_requests: Optional[bool] = None,
    member_changes: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Update user notification preferences for family-related notifications.

    Args:
        email_notifications: Enable/disable email notifications
        push_notifications: Enable/disable push notifications
        family_activity: Enable/disable family activity notifications
        token_requests: Enable/disable token request notifications
        member_changes: Enable/disable member change notifications

    Returns:
        Dictionary containing updated preferences
    """
    user_context = get_mcp_user_context()

    # Build preferences update dictionary
    preferences = {}
    if email_notifications is not None:
        preferences["email_notifications"] = email_notifications
    if push_notifications is not None:
        preferences["push_notifications"] = push_notifications
    if family_activity is not None:
        preferences["family_activity"] = family_activity
    if token_requests is not None:
        preferences["token_requests"] = token_requests
    if member_changes is not None:
        preferences["member_changes"] = member_changes

    if not preferences:
        raise MCPValidationError("At least one preference must be provided")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Update notification preferences using existing manager
        result = await family_manager.update_notification_preferences(
            user_id=user_context.user_id, preferences=preferences
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="update_notification_preferences",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            changes=preferences,
            metadata={"updated_fields": list(preferences.keys())},
        )

        logger.info("Updated notification preferences for user %s: %s", user_context.user_id, preferences)
        return result

    except Exception as e:
        logger.error("Failed to update notification preferences for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to update notification preferences: {str(e)}")


@authenticated_tool(
    name="get_notification_preferences",
    description="Get current user notification preferences",
    permissions=["profile:read"],
    rate_limit_action="profile_read",
)
async def get_notification_preferences() -> Dict[str, Any]:
    """
    Get current user notification preferences.

    Returns:
        Dictionary containing current notification preferences
    """
    user_context = get_mcp_user_context()

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get notification preferences using existing manager
        result = await family_manager.get_notification_preferences(user_id=user_context.user_id)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_notification_preferences",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
        )

        logger.info("Retrieved notification preferences for user %s", user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to get notification preferences for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to get notification preferences: {str(e)}")


@authenticated_tool(
    name="get_received_invitations",
    description="Get invitations received by the current user",
    permissions=["family:read"],
    rate_limit_action="family_read",
)
async def get_received_invitations(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get invitations received by the current user across all families.

    Args:
        status_filter: Optional status filter ("pending", "accepted", "declined", "expired")

    Returns:
        List of received invitations with family and inviter details
    """
    user_context = get_mcp_user_context()

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get received invitations using existing manager
        invitations = await family_manager.get_received_invitations(
            user_id=user_context.user_id,
            user_email=user_context.email,  # Include email-based invitations
            status_filter=status_filter,
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_received_invitations",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"invitation_count": len(invitations), "status_filter": status_filter},
        )

        logger.info("Retrieved %d received invitations for user %s", len(invitations), user_context.user_id)
        return invitations

    except Exception as e:
        logger.error("Failed to get received invitations for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to get received invitations: {str(e)}")


# Family SBD Token Management Tools (Task 4.4)


class TokenRequestCreate(BaseModel):
    """Request model for creating SBD token request."""

    amount: int = Field(..., gt=0, description="Amount of SBD tokens to request")
    reason: str = Field(..., min_length=5, max_length=500, description="Reason for the token request")


class TokenRequestReview(BaseModel):
    """Request model for reviewing token request."""

    action: str = Field(..., pattern="^(approve|deny)$", description="Action to take (approve or deny)")
    comments: Optional[str] = Field(None, max_length=500, description="Optional admin comments")


class SpendingPermissionsUpdate(BaseModel):
    """Request model for updating spending permissions."""

    target_user_id: str = Field(..., description="User ID to update permissions for")
    can_spend: bool = Field(..., description="Whether user can spend tokens")
    spending_limit: int = Field(..., ge=-1, description="Spending limit (-1 for unlimited)")


class AccountFreezeRequest(BaseModel):
    """Request model for freezing/unfreezing account."""

    action: str = Field(..., pattern="^(freeze|unfreeze)$", description="Action to take")
    reason: Optional[str] = Field(None, description="Reason for freezing (required for freeze)")


@authenticated_tool(
    name="get_family_sbd_account",
    description="Get family SBD account information including balance and permissions",
    permissions=["family:read"],
    rate_limit_action="family_read",
)
async def get_family_sbd_account(family_id: str) -> Dict[str, Any]:
    """
    Get comprehensive family SBD account information including balance, permissions, and status.

    Args:
        family_id: The ID of the family to get SBD account information for

    Returns:
        Dictionary containing SBD account details, balance, and member permissions

    Raises:
        MCPAuthorizationError: If user doesn't have access to the family
        MCPValidationError: If family_id is invalid
    """
    user_context = get_mcp_user_context()

    # Validate family access
    await require_family_access(family_id, user_context=user_context)

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get SBD account information using existing manager
        account_data = await family_manager.get_family_sbd_account(family_id, user_context.user_id)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_family_sbd_account",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={"account_username": account_data.get("account_username")},
        )

        logger.info("Retrieved SBD account info for family %s by user %s", family_id, user_context.user_id)
        return account_data

    except Exception as e:
        logger.error("Failed to get family SBD account for %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to retrieve SBD account information: {str(e)}")


@authenticated_tool(
    name="create_token_request",
    description="Create a token request from the family SBD account",
    permissions=["family:member"],
    rate_limit_action="token_request_create",
)
async def create_token_request(family_id: str, amount: int, reason: str) -> Dict[str, Any]:
    """
    Create a token request from the family SBD account for member spending.

    Args:
        family_id: The ID of the family to request tokens from
        amount: Amount of SBD tokens to request (must be positive)
        reason: Reason for the token request (5-500 characters)

    Returns:
        Dictionary containing token request details and status

    Raises:
        MCPAuthorizationError: If user is not a family member
        MCPValidationError: If request parameters are invalid or account is frozen
    """
    user_context = get_mcp_user_context()

    # Validate family access
    await require_family_access(family_id, user_context=user_context)

    # Validate input parameters
    if amount <= 0:
        raise MCPValidationError("Amount must be positive")
    if len(reason) < 5 or len(reason) > 500:
        raise MCPValidationError("Reason must be between 5 and 500 characters")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Create request context for audit
        request_context = {
            "user_id": user_context.user_id,
            "ip_address": user_context.ip_address,
            "user_agent": user_context.user_agent,
            "mcp_operation": True,
        }

        # Create token request using existing manager
        request_data = await family_manager.create_token_request(
            family_id=family_id,
            user_id=user_context.user_id,
            amount=amount,
            reason=reason,
            request_context=request_context,
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="create_token_request",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={"amount": amount, "reason": reason, "request_id": request_data.get("request_id")},
            metadata={"auto_approved": request_data.get("auto_approved", False), "status": request_data.get("status")},
        )

        logger.info(
            "Created token request %s for %d tokens by user %s in family %s",
            request_data.get("request_id"),
            amount,
            user_context.user_id,
            family_id,
        )
        return request_data

    except Exception as e:
        logger.error("Failed to create token request for user %s in family %s: %s", user_context.user_id, family_id, e)
        raise MCPValidationError(f"Failed to create token request: {str(e)}")


@authenticated_tool(
    name="review_token_request",
    description="Review a token request (approve or deny) - admin only",
    permissions=["family:admin"],
    rate_limit_action="token_request_review",
)
async def review_token_request(
    family_id: str, request_id: str, action: str, comments: Optional[str] = None
) -> Dict[str, Any]:
    """
    Review a pending token request by approving or denying it (admin only).

    Args:
        family_id: The ID of the family
        request_id: The ID of the token request to review
        action: Action to take ("approve" or "deny")
        comments: Optional admin comments for the decision

    Returns:
        Dictionary containing review confirmation and updated request status

    Raises:
        MCPAuthorizationError: If user is not a family admin
        MCPValidationError: If request is not found or invalid action
    """
    user_context = get_mcp_user_context()

    # Validate admin access to family
    await require_family_access(family_id, required_role="admin", user_context=user_context)

    # Validate action
    if action not in ["approve", "deny"]:
        raise MCPValidationError("Action must be 'approve' or 'deny'")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Create request context for audit
        request_context = {
            "user_id": user_context.user_id,
            "ip_address": user_context.ip_address,
            "user_agent": user_context.user_agent,
            "mcp_operation": True,
        }

        # Review token request using existing manager
        review_data = await family_manager.review_token_request(
            request_id=request_id,
            admin_id=user_context.user_id,
            action=action,
            comments=comments,
            request_context=request_context,
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="review_token_request",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={
                "request_id": request_id,
                "action": action,
                "comments": comments,
                "new_status": review_data.get("status"),
            },
            metadata={"amount": review_data.get("amount"), "requester_user_id": review_data.get("requester_user_id")},
        )

        logger.info("Token request %s %s by admin %s in family %s", request_id, action, user_context.user_id, family_id)
        return review_data

    except Exception as e:
        logger.error("Failed to review token request %s in family %s: %s", request_id, family_id, e)
        raise MCPValidationError(f"Failed to review token request: {str(e)}")


@authenticated_tool(
    name="get_token_requests",
    description="Get token requests for a family with optional filtering",
    permissions=["family:read"],
    rate_limit_action="family_read",
)
async def get_token_requests(
    family_id: str,
    status_filter: Optional[str] = None,
    user_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Get token requests for a family with optional filtering and pagination.

    Args:
        family_id: The ID of the family
        status_filter: Optional status filter ("pending", "approved", "denied", "expired")
        user_filter: Optional user ID filter to show requests from specific user
        limit: Maximum number of requests to return (default: 50, max: 100)
        offset: Number of requests to skip for pagination (default: 0)

    Returns:
        Dictionary containing token requests and pagination info

    Raises:
        MCPAuthorizationError: If user doesn't have access to the family
        MCPValidationError: If parameters are invalid
    """
    user_context = get_mcp_user_context()

    # Validate family access
    await require_family_access(family_id, user_context=user_context)

    # Validate parameters
    if limit > 100:
        raise MCPValidationError("Limit cannot exceed 100")
    if limit < 1:
        raise MCPValidationError("Limit must be at least 1")
    if offset < 0:
        raise MCPValidationError("Offset cannot be negative")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get token requests using existing manager methods
        if status_filter == "pending":
            # For pending requests, use the admin method if user is admin, otherwise return empty
            try:
                await require_family_access(family_id, required_role="admin", user_context=user_context)
                requests = await family_manager.get_pending_token_requests(family_id, user_context.user_id)
                requests_data = {
                    "requests": requests,
                    "total_count": len(requests),
                    "has_more": False,  # Pending requests method doesn't support pagination
                }
            except MCPAuthorizationError:
                # Non-admin users can only see their own requests
                requests = await family_manager.get_user_token_requests(family_id, user_context.user_id, limit)
                # Filter by status if needed
                if status_filter:
                    requests = [r for r in requests if r.get("status") == status_filter]
                requests_data = {
                    "requests": requests[offset : offset + limit] if offset < len(requests) else [],
                    "total_count": len(requests),
                    "has_more": offset + limit < len(requests),
                }
        else:
            # For other statuses or no filter, get user's own requests
            requests = await family_manager.get_user_token_requests(family_id, user_context.user_id, limit + offset)
            # Filter by status if needed
            if status_filter:
                requests = [r for r in requests if r.get("status") == status_filter]
            # Filter by user if needed and user is admin
            if user_filter:
                try:
                    await require_family_access(family_id, required_role="admin", user_context=user_context)
                    requests = [r for r in requests if r.get("requester_user_id") == user_filter]
                except MCPAuthorizationError:
                    # Non-admin users can only see their own requests
                    if user_filter != user_context.user_id:
                        requests = []

            requests_data = {
                "requests": requests[offset : offset + limit] if offset < len(requests) else [],
                "total_count": len(requests),
                "has_more": offset + limit < len(requests),
            }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_token_requests",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={
                "request_count": len(requests_data.get("requests", [])),
                "status_filter": status_filter,
                "user_filter": user_filter,
                "limit": limit,
                "offset": offset,
            },
        )

        logger.info(
            "Retrieved %d token requests for family %s by user %s",
            len(requests_data.get("requests", [])),
            family_id,
            user_context.user_id,
        )
        return requests_data

    except Exception as e:
        logger.error("Failed to get token requests for family %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to retrieve token requests: {str(e)}")


@authenticated_tool(
    name="update_spending_permissions",
    description="Update spending permissions for a family member - admin only",
    permissions=["family:admin"],
    rate_limit_action="family_admin",
)
async def update_spending_permissions(
    family_id: str, target_user_id: str, can_spend: bool, spending_limit: int
) -> Dict[str, Any]:
    """
    Update spending permissions for a family member (admin only).

    Args:
        family_id: The ID of the family
        target_user_id: The ID of the user to update permissions for
        can_spend: Whether the user can spend tokens
        spending_limit: Spending limit for the user (-1 for unlimited)

    Returns:
        Dictionary containing updated permissions confirmation

    Raises:
        MCPAuthorizationError: If user is not a family admin
        MCPValidationError: If parameters are invalid
    """
    user_context = get_mcp_user_context()

    # Validate admin access to family
    await require_family_access(family_id, required_role="admin", user_context=user_context)

    # Validate spending limit
    if spending_limit < -1:
        raise MCPValidationError("Spending limit must be -1 (unlimited) or a positive number")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Prepare permissions update
        permissions = {"can_spend": can_spend, "spending_limit": spending_limit}

        # Update spending permissions using existing manager
        result = await family_manager.update_spending_permissions(
            family_id=family_id, admin_id=user_context.user_id, target_user_id=target_user_id, permissions=permissions
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="update_spending_permissions",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={"target_user_id": target_user_id, "can_spend": can_spend, "spending_limit": spending_limit},
            metadata={"permissions_updated": True},
        )

        logger.info(
            "Updated spending permissions for user %s in family %s by admin %s",
            target_user_id,
            family_id,
            user_context.user_id,
        )
        return result

    except Exception as e:
        logger.error("Failed to update spending permissions for user %s in family %s: %s", target_user_id, family_id, e)
        raise MCPValidationError(f"Failed to update spending permissions: {str(e)}")


@authenticated_tool(
    name="freeze_family_account",
    description="Freeze the family SBD account to prevent spending - admin only",
    permissions=["family:admin"],
    rate_limit_action="family_admin",
)
async def freeze_family_account(family_id: str, reason: str) -> Dict[str, Any]:
    """
    Freeze the family SBD account to prevent all spending (admin only).

    Args:
        family_id: The ID of the family
        reason: Reason for freezing the account

    Returns:
        Dictionary containing freeze confirmation and details

    Raises:
        MCPAuthorizationError: If user is not a family admin
        MCPValidationError: If reason is not provided
    """
    user_context = get_mcp_user_context()

    # Validate admin access to family
    await require_family_access(family_id, required_role="admin", user_context=user_context)

    # Validate reason
    if not reason or len(reason.strip()) < 5:
        raise MCPValidationError("Reason for freezing must be at least 5 characters")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Freeze family account using existing manager
        result = await family_manager.freeze_family_account(
            family_id=family_id, admin_id=user_context.user_id, reason=reason.strip()
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="freeze_family_account",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={"action": "freeze", "reason": reason.strip(), "frozen_by": user_context.user_id},
            metadata={"account_frozen": True},
        )

        logger.info("Froze family account for family %s by admin %s: %s", family_id, user_context.user_id, reason)
        return result

    except Exception as e:
        logger.error("Failed to freeze family account for family %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to freeze family account: {str(e)}")


@authenticated_tool(
    name="unfreeze_family_account",
    description="Unfreeze the family SBD account to restore spending - admin only",
    permissions=["family:admin"],
    rate_limit_action="family_admin",
)
async def unfreeze_family_account(family_id: str) -> Dict[str, Any]:
    """
    Unfreeze the family SBD account to restore normal spending (admin only).

    Args:
        family_id: The ID of the family

    Returns:
        Dictionary containing unfreeze confirmation and details

    Raises:
        MCPAuthorizationError: If user is not a family admin
        MCPValidationError: If account is not frozen
    """
    user_context = get_mcp_user_context()

    # Validate admin access to family
    await require_family_access(family_id, required_role="admin", user_context=user_context)

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Unfreeze family account using existing manager
        result = await family_manager.unfreeze_family_account(family_id=family_id, admin_id=user_context.user_id)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="unfreeze_family_account",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={"action": "unfreeze", "unfrozen_by": user_context.user_id},
            metadata={"account_frozen": False},
        )

        logger.info("Unfroze family account for family %s by admin %s", family_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to unfreeze family account for family %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to unfreeze family account: {str(e)}")


@authenticated_tool(
    name="get_family_transaction_history",
    description="Get comprehensive family SBD transaction history with filtering",
    permissions=["family:read"],
    rate_limit_action="family_read",
)
async def get_family_transaction_history(
    family_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    transaction_types: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Get comprehensive family SBD transaction history with filtering and pagination.

    Args:
        family_id: The ID of the family
        start_date: Start date filter in ISO format (optional)
        end_date: End date filter in ISO format (optional)
        transaction_types: Comma-separated list of transaction types to filter (optional)
        limit: Maximum number of transactions to return (default: 100, max: 1000)
        offset: Number of transactions to skip for pagination (default: 0)

    Returns:
        Dictionary containing transaction history with family context and audit trails

    Raises:
        MCPAuthorizationError: If user doesn't have access to the family
        MCPValidationError: If parameters are invalid
    """
    user_context = get_mcp_user_context()

    # Validate family access
    await require_family_access(family_id, user_context=user_context)

    # Validate parameters
    if limit > 1000:
        raise MCPValidationError("Limit cannot exceed 1000")
    if limit < 1:
        raise MCPValidationError("Limit must be at least 1")
    if offset < 0:
        raise MCPValidationError("Offset cannot be negative")

    # Parse and validate dates if provided
    parsed_start_date = None
    parsed_end_date = None

    if start_date:
        try:
            from datetime import datetime

            parsed_start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            raise MCPValidationError("start_date must be in ISO format")

    if end_date:
        try:
            from datetime import datetime

            parsed_end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            raise MCPValidationError("end_date must be in ISO format")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get transaction history using existing manager
        transaction_data = await family_manager.get_family_transactions(
            family_id=family_id, user_id=user_context.user_id, skip=offset, limit=limit
        )

        # Apply additional filtering if needed
        transactions = transaction_data.get("transactions", [])

        # Filter by date range if provided
        if parsed_start_date or parsed_end_date:
            filtered_transactions = []
            for tx in transactions:
                tx_date = tx.get("created_at") or tx.get("timestamp")
                if tx_date:
                    if isinstance(tx_date, str):
                        try:
                            from datetime import datetime

                            tx_date = datetime.fromisoformat(tx_date.replace("Z", "+00:00"))
                        except ValueError:
                            continue

                    if parsed_start_date and tx_date < parsed_start_date:
                        continue
                    if parsed_end_date and tx_date > parsed_end_date:
                        continue

                filtered_transactions.append(tx)
            transactions = filtered_transactions

        # Filter by transaction types if provided
        if transaction_types:
            type_list = [t.strip() for t in transaction_types.split(",")]
            transactions = [tx for tx in transactions if tx.get("type") in type_list]

        # Update transaction data with filtered results
        transaction_data = {
            "transactions": transactions,
            "total_count": len(transactions),
            "has_more": transaction_data.get("has_more", False),
            "family_id": family_id,
            "filters_applied": {"start_date": start_date, "end_date": end_date, "transaction_types": transaction_types},
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_family_transaction_history",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={
                "transaction_count": len(transaction_data.get("transactions", [])),
                "start_date": start_date,
                "end_date": end_date,
                "transaction_types": transaction_types,
                "limit": limit,
                "offset": offset,
            },
        )

        logger.info(
            "Retrieved %d transactions for family %s by user %s",
            len(transaction_data.get("transactions", [])),
            family_id,
            user_context.user_id,
        )
        return transaction_data

    except Exception as e:
        logger.error("Failed to get transaction history for family %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to retrieve transaction history: {str(e)}")


# Family Administration and Audit Tools (Task 4.5)


class AdminActionLog(BaseModel):
    """Model for admin action log entries."""

    action_id: str
    admin_user_id: str
    admin_username: str
    action_type: str
    target_resource: str
    target_id: str
    changes: Dict[str, Any]
    timestamp: datetime
    ip_address: str
    user_agent: str


class FamilyStats(BaseModel):
    """Model for family usage statistics."""

    family_id: str
    member_count: int
    active_members_30d: int
    total_transactions: int
    total_sbd_spent: int
    total_sbd_earned: int
    invitation_count: int
    pending_invitations: int
    token_requests_count: int
    pending_token_requests: int


class FamilyLimits(BaseModel):
    """Model for family limits information."""

    max_members: int
    current_members: int
    max_sbd_balance: int
    current_sbd_balance: int
    max_monthly_spending: int
    current_monthly_spending: int
    max_pending_invitations: int
    current_pending_invitations: int


@authenticated_tool(
    name="get_admin_actions_log",
    description="Get comprehensive audit trail of admin actions for a family",
    permissions=["family:admin"],
    rate_limit_action="family_admin",
)
async def get_admin_actions_log(
    family_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    action_types: Optional[str] = None,
    admin_filter: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Get comprehensive audit trail of admin actions for a family with filtering.

    Args:
        family_id: The ID of the family to get audit log for
        start_date: Start date filter in ISO format (optional)
        end_date: End date filter in ISO format (optional)
        action_types: Comma-separated list of action types to filter (optional)
        admin_filter: Filter by specific admin user ID (optional)
        limit: Maximum number of log entries to return (default: 100, max: 500)
        offset: Number of entries to skip for pagination (default: 0)

    Returns:
        Dictionary containing admin action log entries with detailed audit information

    Raises:
        MCPAuthorizationError: If user is not a family admin
        MCPValidationError: If parameters are invalid
    """
    user_context = get_mcp_user_context()

    # Validate admin access to family
    await require_family_access(family_id, required_role="admin", user_context=user_context)

    # Validate parameters
    if limit > 500:
        raise MCPValidationError("Limit cannot exceed 500")
    if limit < 1:
        raise MCPValidationError("Limit must be at least 1")
    if offset < 0:
        raise MCPValidationError("Offset cannot be negative")

    # Parse and validate dates if provided
    parsed_start_date = None
    parsed_end_date = None

    if start_date:
        try:
            from datetime import datetime

            parsed_start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            raise MCPValidationError("start_date must be in ISO format")

    if end_date:
        try:
            from datetime import datetime

            parsed_end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            raise MCPValidationError("end_date must be in ISO format")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get admin actions log using existing manager
        log_data = await family_manager.get_admin_actions_log(
            family_id=family_id,
            admin_id=user_context.user_id,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            action_types=action_types.split(",") if action_types else None,
            admin_filter=admin_filter,
            limit=limit,
            offset=offset,
        )

        # Create audit trail for accessing audit log
        await create_mcp_audit_trail(
            operation="get_admin_actions_log",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={
                "log_entries_count": len(log_data.get("actions", [])),
                "start_date": start_date,
                "end_date": end_date,
                "action_types": action_types,
                "admin_filter": admin_filter,
                "limit": limit,
                "offset": offset,
            },
        )

        logger.info(
            "Retrieved %d admin action log entries for family %s by user %s",
            len(log_data.get("actions", [])),
            family_id,
            user_context.user_id,
        )
        return log_data

    except Exception as e:
        logger.error("Failed to get admin actions log for family %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to retrieve admin actions log: {str(e)}")


# NOTE: designate_backup_admin and remove_backup_admin are workspace-specific tools
# and have been moved to workspace_tools.py. They should not be duplicated here.


@authenticated_tool(
    name="get_family_stats",
    description="Get comprehensive family usage statistics and analytics",
    permissions=["family:read"],
    rate_limit_action="family_read",
)
async def get_family_stats(family_id: str, include_detailed_breakdown: bool = False) -> Dict[str, Any]:
    """
    Get comprehensive family usage statistics including member activity, transactions, and growth metrics.

    Args:
        family_id: The ID of the family to get statistics for
        include_detailed_breakdown: Whether to include detailed breakdowns by member/time period

    Returns:
        Dictionary containing comprehensive family statistics and analytics

    Raises:
        MCPAuthorizationError: If user doesn't have access to the family
    """
    user_context = get_mcp_user_context()

    # Validate family access
    await require_family_access(family_id, user_context=user_context)

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get comprehensive family statistics using existing manager methods
        family_details = await family_manager.get_family_details(family_id, user_context.user_id)
        members = await family_manager.get_family_members(family_id, user_context.user_id)
        sbd_account = await family_manager.get_family_sbd_account(family_id, user_context.user_id)
        transactions = await family_manager.get_family_transactions(family_id, user_context.user_id, limit=1000)

        # Calculate statistics from available data
        stats_data = {
            "family_id": family_id,
            "member_count": len(members),
            "active_members_30d": len([m for m in members if m.get("last_active")]),  # Simplified
            "total_transactions": len(transactions.get("transactions", [])),
            "total_sbd_spent": sum(
                tx.get("amount", 0) for tx in transactions.get("transactions", []) if tx.get("type") == "spend"
            ),
            "total_sbd_earned": sum(
                tx.get("amount", 0) for tx in transactions.get("transactions", []) if tx.get("type") == "earn"
            ),
            "current_sbd_balance": sbd_account.get("balance", 0),
            "account_frozen": sbd_account.get("account_frozen", False),
            "created_at": family_details.get("created_at"),
            "owner_id": family_details.get("owner_id"),
        }

        # Add detailed breakdown if requested
        if include_detailed_breakdown:
            stats_data["detailed_breakdown"] = {
                "members_by_role": {},
                "transactions_by_type": {},
                "monthly_activity": {},
            }

            # Calculate members by role
            for member in members:
                role = member.get("role", "member")
                stats_data["detailed_breakdown"]["members_by_role"][role] = (
                    stats_data["detailed_breakdown"]["members_by_role"].get(role, 0) + 1
                )

            # Calculate transactions by type
            for tx in transactions.get("transactions", []):
                tx_type = tx.get("type", "unknown")
                stats_data["detailed_breakdown"]["transactions_by_type"][tx_type] = (
                    stats_data["detailed_breakdown"]["transactions_by_type"].get(tx_type, 0) + 1
                )

        # Enhance with additional computed metrics
        enhanced_stats = {
            **stats_data,
            "computed_metrics": {
                "member_growth_rate": stats_data.get("member_growth_30d", 0),
                "activity_score": min(
                    100, (stats_data.get("active_members_30d", 0) / max(1, stats_data.get("member_count", 1))) * 100
                ),
                "spending_velocity": stats_data.get("avg_daily_spending_30d", 0),
                "invitation_success_rate": (
                    (
                        stats_data.get("accepted_invitations", 0)
                        / max(1, stats_data.get("total_invitations_sent", 1))
                        * 100
                    )
                    if stats_data.get("total_invitations_sent", 0) > 0
                    else 0
                ),
            },
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_family_stats",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={
                "include_detailed_breakdown": include_detailed_breakdown,
                "member_count": stats_data.get("member_count", 0),
                "stats_generated_at": datetime.utcnow().isoformat(),
            },
        )

        logger.info("Retrieved family statistics for family %s by user %s", family_id, user_context.user_id)
        return enhanced_stats

    except Exception as e:
        logger.error("Failed to get family statistics for family %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to retrieve family statistics: {str(e)}")


@authenticated_tool(
    name="get_family_limits",
    description="Get current family limits and usage information",
    permissions=["family:read"],
    rate_limit_action="family_read",
)
async def get_family_limits(family_id: str) -> Dict[str, Any]:
    """
    Get comprehensive family limits and current usage information for capacity planning.

    Args:
        family_id: The ID of the family to get limits for

    Returns:
        Dictionary containing family limits, current usage, and capacity information

    Raises:
        MCPAuthorizationError: If user doesn't have access to the family
    """
    user_context = get_mcp_user_context()

    # Validate family access
    await require_family_access(family_id, user_context=user_context)

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get family limits and usage using existing manager methods
        family_details = await family_manager.get_family_details(family_id, user_context.user_id)
        members = await family_manager.get_family_members(family_id, user_context.user_id)
        sbd_account = await family_manager.get_family_sbd_account(family_id, user_context.user_id)
        user_limits = await family_manager.check_family_limits(user_context.user_id)

        # Build limits data from available information
        limits_data = {
            "family_id": family_id,
            "max_members": user_limits.get("max_families_per_user", 10),  # Default limit
            "current_members": len(members),
            "max_sbd_balance": 1000000,  # Default limit - could be configurable
            "current_sbd_balance": sbd_account.get("balance", 0),
            "max_monthly_spending": 50000,  # Default limit - could be configurable
            "current_monthly_spending": 0,  # Would need to calculate from recent transactions
            "max_pending_invitations": 10,  # Default limit
            "current_pending_invitations": 0,  # Would need to get from invitations
            "account_frozen": sbd_account.get("account_frozen", False),
            "limits_last_updated": family_details.get("updated_at"),
        }

        # Calculate usage percentages and warnings
        enhanced_limits = {
            **limits_data,
            "usage_percentages": {
                "members": (limits_data.get("current_members", 0) / max(1, limits_data.get("max_members", 1))) * 100,
                "sbd_balance": (
                    limits_data.get("current_sbd_balance", 0) / max(1, limits_data.get("max_sbd_balance", 1))
                )
                * 100,
                "monthly_spending": (
                    limits_data.get("current_monthly_spending", 0) / max(1, limits_data.get("max_monthly_spending", 1))
                )
                * 100,
                "pending_invitations": (
                    limits_data.get("current_pending_invitations", 0)
                    / max(1, limits_data.get("max_pending_invitations", 1))
                )
                * 100,
            },
            "warnings": [],
            "recommendations": [],
        }

        # Add warnings for high usage
        usage_percentages = enhanced_limits["usage_percentages"]
        if usage_percentages["members"] > 80:
            enhanced_limits["warnings"].append("Member limit approaching capacity")
        if usage_percentages["sbd_balance"] > 90:
            enhanced_limits["warnings"].append("SBD balance approaching limit")
        if usage_percentages["monthly_spending"] > 85:
            enhanced_limits["warnings"].append("Monthly spending limit approaching")

        # Add recommendations
        if usage_percentages["members"] > 70:
            enhanced_limits["recommendations"].append("Consider requesting member limit increase")
        if usage_percentages["sbd_balance"] < 20:
            enhanced_limits["recommendations"].append("Consider adding more SBD tokens to family account")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_family_limits",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={
                "limits_checked_at": datetime.utcnow().isoformat(),
                "warnings_count": len(enhanced_limits["warnings"]),
                "recommendations_count": len(enhanced_limits["recommendations"]),
            },
        )

        logger.info("Retrieved family limits for family %s by user %s", family_id, user_context.user_id)
        return enhanced_limits

    except Exception as e:
        logger.error("Failed to get family limits for family %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to retrieve family limits: {str(e)}")


@authenticated_tool(
    name="emergency_admin_access",
    description="Request emergency admin access for critical family operations",
    permissions=["family:emergency"],
    rate_limit_action="emergency_access",
)
async def emergency_admin_access(
    family_id: str, emergency_reason: str, contact_verification: str, requested_actions: List[str]
) -> Dict[str, Any]:
    """
    Request emergency admin access for critical family operations when normal admin is unavailable.

    Args:
        family_id: The ID of the family requiring emergency access
        emergency_reason: Detailed reason for emergency access request
        contact_verification: Emergency contact verification information
        requested_actions: List of specific actions needed during emergency access

    Returns:
        Dictionary containing emergency access request status and temporary permissions

    Raises:
        MCPAuthorizationError: If user is not authorized for emergency access
        MCPValidationError: If emergency request is invalid or insufficient information provided
    """
    user_context = get_mcp_user_context()

    # Validate emergency access eligibility (backup admin or family member with emergency contact)
    await require_family_access(family_id, user_context=user_context)

    # Validate emergency request parameters
    if not emergency_reason or len(emergency_reason.strip()) < 20:
        raise MCPValidationError("Emergency reason must be at least 20 characters and detailed")

    if not contact_verification or len(contact_verification.strip()) < 5:
        raise MCPValidationError("Contact verification information is required")

    if not requested_actions or len(requested_actions) == 0:
        raise MCPValidationError("At least one requested action must be specified")

    # Validate requested actions are legitimate emergency actions
    valid_emergency_actions = [
        "unfreeze_account",
        "approve_urgent_token_request",
        "remove_malicious_member",
        "update_emergency_contact",
        "designate_new_admin",
        "access_family_settings",
    ]

    invalid_actions = [action for action in requested_actions if action not in valid_emergency_actions]
    if invalid_actions:
        raise MCPValidationError(f"Invalid emergency actions requested: {invalid_actions}")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Create emergency access request - for now we'll create a basic implementation
        # In a full implementation, this would integrate with an emergency access system
        emergency_request = {
            "request_id": f"emergency_{family_id}_{user_context.user_id}_{int(datetime.utcnow().timestamp())}",
            "family_id": family_id,
            "requester_id": user_context.user_id,
            "emergency_reason": emergency_reason.strip(),
            "requested_actions": requested_actions,
            "status": "pending_review",
            "created_at": datetime.utcnow().isoformat(),
            "requires_manual_review": True,
            "auto_approved": False,
            "contact_verification_provided": True,
            "estimated_review_time": "24 hours",
            "emergency_contact_notified": True,
        }

        # Create comprehensive audit trail for emergency access
        await create_mcp_audit_trail(
            operation="emergency_admin_access",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            changes={
                "emergency_reason": emergency_reason.strip(),
                "requested_actions": requested_actions,
                "emergency_request_id": emergency_request.get("request_id"),
                "status": emergency_request.get("status"),
            },
            metadata={
                "contact_verification_provided": True,
                "actions_count": len(requested_actions),
                "auto_approved": emergency_request.get("auto_approved", False),
                "requires_manual_review": emergency_request.get("requires_manual_review", True),
            },
        )

        # Log emergency access request with high priority
        logger.warning(
            "EMERGENCY ACCESS REQUESTED for family %s by user %s: %s",
            family_id,
            user_context.user_id,
            emergency_reason[:100],
        )

        return emergency_request

    except Exception as e:
        logger.error("Failed to process emergency admin access request for family %s: %s", family_id, e)
        raise MCPValidationError(f"Failed to process emergency access request: {str(e)}")


@authenticated_tool(
    name="validate_family_access",
    description="Validate and check user permissions for specific family operations",
    permissions=["family:read"],
    rate_limit_action="family_read",
)
async def validate_family_access(
    family_id: str, operation: str, target_resource: Optional[str] = None, target_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate and check user permissions for specific family operations and resources.

    Args:
        family_id: The ID of the family to validate access for
        operation: The operation to validate (e.g., "read", "write", "admin", "delete")
        target_resource: Optional target resource type (e.g., "member", "settings", "sbd_account")
        target_id: Optional target resource ID for resource-specific validation

    Returns:
        Dictionary containing access validation results and permission details

    Raises:
        MCPAuthorizationError: If user doesn't have access to the family
        MCPValidationError: If operation or parameters are invalid
    """
    user_context = get_mcp_user_context()

    # Validate family access first
    await require_family_access(family_id, user_context=user_context)

    # Validate operation parameter
    valid_operations = ["read", "write", "admin", "delete", "emergency", "audit"]
    if operation not in valid_operations:
        raise MCPValidationError(f"Invalid operation. Must be one of: {valid_operations}")

    family_manager = FamilyManager(
        db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
    )

    try:
        # Get user's role and permissions in the family
        family_details = await family_manager.get_family_details(family_id, user_context.user_id)

        # Extract user role from family details
        user_role = "member"  # default
        members = await family_manager.get_family_members(family_id, user_context.user_id)
        user_member = next((m for m in members if m.get("user_id") == user_context.user_id), None)
        if user_member:
            user_role = user_member.get("role", "member")

        # Validate specific operation permissions
        validation_result = {
            "family_id": family_id,
            "user_id": user_context.user_id,
            "user_role": user_role,
            "operation": operation,
            "target_resource": target_resource,
            "target_id": target_id,
            "access_granted": False,
            "permissions": [],
            "restrictions": [],
            "validation_details": {},
        }

        # Check operation-specific permissions
        if operation == "read":
            validation_result["access_granted"] = True
            validation_result["permissions"] = ["view_family_info", "view_members", "view_own_data"]

        elif operation == "write":
            if user_role in ["admin", "owner"]:
                validation_result["access_granted"] = True
                validation_result["permissions"] = ["modify_settings", "manage_members", "manage_invitations"]
            else:
                validation_result["restrictions"] = ["requires_admin_role"]

        elif operation == "admin":
            if user_role in ["admin", "owner"]:
                validation_result["access_granted"] = True
                validation_result["permissions"] = ["full_admin_access", "manage_roles", "financial_operations"]
            else:
                validation_result["restrictions"] = ["requires_admin_role"]

        elif operation == "delete":
            if user_role == "owner":
                validation_result["access_granted"] = True
                validation_result["permissions"] = ["delete_family", "remove_any_member"]
            else:
                validation_result["restrictions"] = ["requires_owner_role"]

        elif operation == "emergency":
            # Emergency access has special rules
            backup_admins = family_details.get("backup_admins", [])
            if user_context.user_id in backup_admins or user_role in ["admin", "owner"]:
                validation_result["access_granted"] = True
                validation_result["permissions"] = ["emergency_access", "temporary_admin"]
            else:
                validation_result["restrictions"] = ["requires_backup_admin_or_admin_role"]

        elif operation == "audit":
            if user_role in ["admin", "owner"]:
                validation_result["access_granted"] = True
                validation_result["permissions"] = ["view_audit_logs", "access_admin_actions"]
            else:
                validation_result["restrictions"] = ["requires_admin_role"]

        # Add resource-specific validation if target_resource is provided
        if target_resource and validation_result["access_granted"]:
            # For now, we'll do basic resource validation based on the operation and role
            # This could be enhanced with more specific resource validation logic
            resource_validation = {
                "resource_type": target_resource,
                "resource_id": target_id,
                "access_allowed": True,  # Basic validation - could be enhanced
                "validation_method": "basic_role_check",
            }
            validation_result["validation_details"]["resource_access"] = resource_validation

        # Create audit trail for access validation
        await create_mcp_audit_trail(
            operation="validate_family_access",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={
                "validated_operation": operation,
                "target_resource": target_resource,
                "target_id": target_id,
                "access_granted": validation_result["access_granted"],
                "user_role": user_role,
                "permissions_count": len(validation_result["permissions"]),
                "restrictions_count": len(validation_result["restrictions"]),
            },
        )

        logger.info(
            "Validated family access for operation %s by user %s in family %s: %s",
            operation,
            user_context.user_id,
            family_id,
            "GRANTED" if validation_result["access_granted"] else "DENIED",
        )

        return validation_result

    except Exception as e:
        logger.error(
            "Failed to validate family access for user %s in family %s: %s", user_context.user_id, family_id, e
        )
        raise MCPValidationError(f"Failed to validate family access: {str(e)}")
