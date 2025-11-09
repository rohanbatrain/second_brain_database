"""
Family MCP Resources

Comprehensive information resources for family entities with real-time data.
Provides family information, member lists, and statistics through MCP resources.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from ....config import settings
from ....managers.family_manager import FamilyManager
from ....managers.logging_manager import get_logger
from ..context import create_mcp_audit_trail, require_family_access
from ..exceptions import MCPAuthorizationError, MCPValidationError
from ..modern_server import mcp
from ..security import get_mcp_user_context

logger = get_logger(prefix="[MCP_FamilyResources]")

# Import manager instances
from ....database import db_manager
from ....managers.redis_manager import redis_manager
from ....managers.security_manager import security_manager


@mcp.resource("family://{family_id}/info", tags={"family", "secure", "production"})
async def get_family_info_resource(family_id: str) -> str:
    """
    Get comprehensive family information as a resource.

    Provides detailed family information including basic details,
    member count, SBD account status, and configuration settings.

    Args:
        family_id: The ID of the family to get information for

    Returns:
        JSON string containing family information

    Raises:
        MCPAuthorizationError: If user doesn't have access to the family
    """
    try:
        user_context = get_mcp_user_context()

        # Validate family access
        await require_family_access(family_id, user_context=user_context)

        # Create family manager instance
        family_manager = FamilyManager(
            db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
        )

        # Get family details
        family_details = await family_manager.get_family_details(family_id, user_context.user_id)

        # Get SBD account information
        sbd_account = await family_manager.get_family_sbd_account(family_id, user_context.user_id)

        # Combine information
        family_info = {
            "id": family_id,
            "name": family_details.get("name"),
            "description": family_details.get("description"),
            "created_at": family_details.get("created_at"),
            "member_count": family_details.get("member_count", 0),
            "owner_id": family_details.get("owner_id"),
            "sbd_account": {
                "username": sbd_account.get("account_username"),
                "frozen": sbd_account.get("account_frozen", False),
                "balance": sbd_account.get("balance", 0),
            },
            "limits": family_details.get("limits", {}),
            "settings": family_details.get("settings", {}),
            "resource_type": "family_info",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_family_info_resource",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={"family_name": family_details.get("name")},
        )

        logger.info("Provided family info resource for family %s to user %s", family_id, user_context.user_id)

        return json.dumps(family_info, indent=2, default=str)

    except Exception as e:
        logger.error("Failed to get family info resource for %s: %s", family_id, e)
        return json.dumps({"error": f"Failed to retrieve family information: {str(e)}"}, indent=2)


@mcp.resource("family://{family_id}/members", tags={"family", "production", "resources", "secure"})
async def get_family_members_resource(family_id: str) -> str:
    """
    Get family member list as a resource with proper access control.

    Provides comprehensive member information including roles,
    relationships, and permissions for authorized users.

    Args:
        family_id: The ID of the family to get members for

    Returns:
        JSON string containing family member list
    """
    try:
        user_context = get_mcp_user_context()

        # Validate family access
        await require_family_access(family_id, user_context=user_context)

        family_manager = FamilyManager(
            db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
        )

        # Get family members
        members = await family_manager.get_family_members(family_id, user_context.user_id)

        # Format member information
        member_list = []
        for member in members:
            member_info = {
                "user_id": member.get("user_id"),
                "username": member.get("username"),
                "email": member.get("email"),
                "role": member.get("role"),
                "joined_at": member.get("joined_at"),
                "relationship": member.get("relationship"),
                "spending_permissions": member.get("spending_permissions", {}),
                "status": member.get("status", "active"),
            }
            member_list.append(member_info)

        result = {
            "family_id": family_id,
            "members": member_list,
            "total_members": len(member_list),
            "resource_type": "family_members",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_family_members_resource",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={"member_count": len(member_list)},
        )

        logger.info("Provided family members resource for family %s to user %s", family_id, user_context.user_id)

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error("Failed to get family members resource for %s: %s", family_id, e)
        return json.dumps({"error": f"Failed to retrieve family members: {str(e)}"}, indent=2)


@mcp.resource("family://{family_id}/statistics", tags={"family", "production", "resources", "secure"})
async def get_family_statistics_resource(family_id: str) -> str:
    """
    Get family usage statistics and analytics as a resource.

    Provides comprehensive statistics including spending patterns,
    activity metrics, and usage analytics for family management.

    Args:
        family_id: The ID of the family to get statistics for

    Returns:
        JSON string containing family statistics
    """
    try:
        user_context = get_mcp_user_context()

        # Validate family access
        await require_family_access(family_id, user_context=user_context)

        family_manager = FamilyManager(
            db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
        )

        # Get family statistics
        stats = await family_manager.get_family_stats(family_id, user_context.user_id)

        result = {
            "family_id": family_id,
            "statistics": stats,
            "resource_type": "family_statistics",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_family_statistics_resource",
            user_context=user_context,
            resource_type="family",
            resource_id=family_id,
            metadata={"stats_requested": True},
        )

        logger.info("Provided family statistics resource for family %s to user %s", family_id, user_context.user_id)

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error("Failed to get family statistics resource for %s: %s", family_id, e)
        return json.dumps({"error": f"Failed to retrieve family statistics: {str(e)}"}, indent=2)
