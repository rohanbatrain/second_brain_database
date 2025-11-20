"""
User MCP Resources

Comprehensive information resources for user entities and profiles.
Provides user information, preferences, and activity data through MCP resources.
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

logger = get_logger(prefix="[MCP_UserResources]")


@mcp.resource("user://{user_id}/profile", tags={"production", "resources", "secure", "user"})
async def get_user_profile_resource(user_id: str) -> str:
    """
    Get user profile information as a resource.

    Args:
        user_id: The ID of the user to get profile for

    Returns:
        JSON string containing user profile information
    """
    try:
        user_context = get_mcp_user_context()

        # Validate user access (users can only access their own profile unless admin)
        if user_context.user_id != user_id and user_context.role != "admin":
            raise MCPAuthorizationError(f"Access denied to user profile {user_id}")

        # Mock user profile data - replace with actual user manager integration
        profile = {
            "user_id": user_id,
            "username": f"user_{user_id}",
            "email": f"user_{user_id}@example.com",
            "created_at": datetime.utcnow().isoformat(),
            "last_login": datetime.utcnow().isoformat(),
            "preferences": {"theme": "dark", "language": "en", "notifications": True},
            "stats": {"families_count": 1, "workspaces_count": 2, "total_sbd_tokens": 100},
        }

        result = {"profile": profile, "resource_type": "user_profile", "last_updated": datetime.utcnow().isoformat()}

        await create_mcp_audit_trail(
            operation="get_user_profile_resource",
            user_context=user_context,
            resource_type="user",
            resource_id=user_id,
            metadata={"profile_accessed": True},
        )

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error("Failed to get user profile resource for %s: %s", user_id, e)
        return json.dumps({"error": f"Failed to retrieve user profile: {str(e)}"}, indent=2)


@mcp.resource("user://current/preferences", tags={"production", "resources", "secure", "user"})
async def get_current_user_preferences_resource() -> str:
    """
    Get current user preferences as a resource.

    Returns:
        JSON string containing user preferences
    """
    try:
        user_context = get_mcp_user_context()

        # Mock preferences data - replace with actual user manager integration
        preferences = {
            "user_id": user_context.user_id,
            "theme": "dark",
            "language": "en",
            "notifications": {"email": True, "push": False, "family_updates": True, "workspace_updates": True},
            "privacy": {"profile_visibility": "family", "activity_tracking": True},
        }

        result = {
            "preferences": preferences,
            "resource_type": "user_preferences",
            "last_updated": datetime.utcnow().isoformat(),
        }

        await create_mcp_audit_trail(
            operation="get_current_user_preferences_resource",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"preferences_accessed": True},
        )

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error("Failed to get user preferences resource: %s", e)
        return json.dumps({"error": f"Failed to retrieve user preferences: {str(e)}"}, indent=2)
