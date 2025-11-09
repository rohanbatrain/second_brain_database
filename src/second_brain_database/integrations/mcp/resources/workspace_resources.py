"""
Workspace MCP Resources

Comprehensive information resources for workspace entities and team collaboration.
Provides workspace information, member data, and project details through MCP resources.
"""

from datetime import datetime
import json
from typing import Any, Dict, List, Optional

from ....config import settings
from ....managers.logging_manager import get_logger
from ..context import create_mcp_audit_trail
from ..exceptions import MCPAuthorizationError, MCPValidationError
from ..modern_server import mcp
from ..security import get_mcp_user_context

logger = get_logger(prefix="[MCP_WorkspaceResources]")


@mcp.resource("workspace://{workspace_id}/info", tags={"production", "resources", "secure", "workspace"})
async def get_workspace_info_resource(workspace_id: str) -> str:
    """
    Get workspace information as a resource.

    Args:
        workspace_id: The ID of the workspace to get information for

    Returns:
        JSON string containing workspace information
    """
    try:
        user_context = get_mcp_user_context()

        # Mock workspace data - replace with actual workspace manager integration
        workspace_info = {
            "workspace_id": workspace_id,
            "name": f"Workspace {workspace_id}",
            "description": "A collaborative workspace",
            "created_at": datetime.utcnow().isoformat(),
            "owner_id": user_context.user_id,
            "member_count": 5,
            "project_count": 3,
            "settings": {"visibility": "private", "collaboration_enabled": True, "notifications_enabled": True},
        }

        result = {
            "workspace": workspace_info,
            "resource_type": "workspace_info",
            "last_updated": datetime.utcnow().isoformat(),
        }

        await create_mcp_audit_trail(
            operation="get_workspace_info_resource",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={"workspace_name": workspace_info["name"]},
        )

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error("Failed to get workspace info resource for %s: %s", workspace_id, e)
        return json.dumps({"error": f"Failed to retrieve workspace information: {str(e)}"}, indent=2)


@mcp.resource("workspace://{workspace_id}/members", tags={"production", "resources", "secure", "workspace"})
async def get_workspace_members_resource(workspace_id: str) -> str:
    """
    Get workspace members as a resource.

    Args:
        workspace_id: The ID of the workspace to get members for

    Returns:
        JSON string containing workspace members
    """
    try:
        user_context = get_mcp_user_context()

        # Mock members data - replace with actual workspace manager integration
        members = [
            {
                "user_id": user_context.user_id,
                "username": f"user_{user_context.user_id}",
                "role": "owner",
                "joined_at": datetime.utcnow().isoformat(),
                "permissions": ["read", "write", "admin"],
            },
            {
                "user_id": "user_002",
                "username": "user_002",
                "role": "member",
                "joined_at": datetime.utcnow().isoformat(),
                "permissions": ["read", "write"],
            },
        ]

        result = {
            "workspace_id": workspace_id,
            "members": members,
            "total_members": len(members),
            "resource_type": "workspace_members",
            "last_updated": datetime.utcnow().isoformat(),
        }

        await create_mcp_audit_trail(
            operation="get_workspace_members_resource",
            user_context=user_context,
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={"member_count": len(members)},
        )

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error("Failed to get workspace members resource for %s: %s", workspace_id, e)
        return json.dumps({"error": f"Failed to retrieve workspace members: {str(e)}"}, indent=2)
