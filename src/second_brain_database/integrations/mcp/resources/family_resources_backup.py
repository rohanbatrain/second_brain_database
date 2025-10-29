"""
Family MCP Resources

Comprehensive information resources for family entities with real-time data.
Provides family information, member lists, and statistics through MCP resources.
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from ....managers.family_manager import FamilyManager
from ....managers.logging_manager import get_logger
from ....config import settings
from ..modern_server import mcp
from ..security import get_mcp_user_context
from ..context import require_family_access, create_mcp_audit_trail
from ..exceptions import MCPAuthorizationError, MCPValidationError

logger = get_logger(prefix="[MCP_FamilyResources]")

# Import manager instances
from ....database import db_manager
from ....managers.security_manager import security_manager
from ....managers.redis_manager import redis_manager

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
                db_manager=db_manager,
                security_manager=security_manager,
                redis_manager=redis_manager
            )
            
            # Get family details
            family_details = await family_manager.get_family_details(family_id, user_context.user_id)
            
            # Get SBD account information
            sbd_account = await family_manager.get_family_sbd_account(family_id, user_context.user_id)
            
            # Create audit trail
            await create_mcp_audit_trail(
                operation="get_family_info_resource",
                user_context=user_context,
                resource_type="family",
                resource_id=family_id,
                metadata={"resource_type": "family_info"}
            )
            
            # Combine information
            family_info = {
                "id": family_id,
                "name": family_details.get("name"),
                "description": family_details.get("description"),
                "created_at": family_details.get("created_at").isoformat() if family_details.get("created_at") else None,
                "member_count": family_details.get("member_count", 0),
                "owner_id": family_details.get("owner_id"),
                "sbd_account": {
                    "username": sbd_account.get("account_username"),
                    "frozen": sbd_account.get("account_frozen", False),
                    "balance": sbd_account.get("balance", 0)
                },
                "limits": family_details.get("limits", {}),
                "settings": family_details.get("settings", {}),
                "last_updated": datetime.utcnow().isoformat()
            }
            
            logger.info("Provided family info resource for family %s to user %s", 
                       family_id, user_context.user_id)
            
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
                db_manager=db_manager,
                security_manager=security_manager,
                redis_manager=redis_manager
            )
            
            # Get family members
            members = await family_manager.get_family_members(family_id, user_context.user_id)
            
            # Get relationships for additional context
            relationships = await family_manager.get_family_relationships(family_id, user_context.user_id)
            
            # Create audit trail
            await create_mcp_audit_trail(
                operation="get_family_members_resource",
                user_context=user_context,
                resource_type="family",
                resource_id=family_id,
                metadata={"resource_type": "family_members", "member_count": len(members)}
            )
            
            # Format member information
            member_list = []
            for member in members:
                # Find relationship info for this member
                member_relationships = [r for r in relationships if r.get("user_id") == member.get("user_id")]
                
                member_info = {
                    "user_id": member.get("user_id"),
                    "username": member.get("username"),
                    "email": member.get("email") if user_context.get_family_role(family_id) in ["admin", "owner"] else None,
                    "role": member.get("role"),
                    "joined_at": member.get("joined_at").isoformat() if member.get("joined_at") else None,
                    "relationship": member_relationships[0].get("relationship") if member_relationships else None,
                    "spending_permissions": member.get("spending_permissions", {}),
                    "last_active": member.get("last_active").isoformat() if member.get("last_active") else None
                }
                member_list.append(member_info)
            
            result = {
                "family_id": family_id,
                "members": member_list,
                "total_members": len(member_list),
                "last_updated": datetime.utcnow().isoformat()
            }
            
            logger.info("Provided family members resource for family %s to user %s (%d members)", 
                       family_id, user_context.user_id, len(member_list))
            
            return json.dumps(result, indent=2, default=str)
            
        except Exception as e:
            logger.error("Failed to get family members resource for %s: %s", family_id, e)
            return json.dumps({"error": f"Failed to retrieve family members: {str(e)}"}, indent=2)


    @mcp.resource("family://{family_id}/statistics", tags={"family", "production", "resources", "secure"})
async def get_family_statistics_resource(family_id: str) -> str:
        """
        Get family statistics and analytics as a resource.
        
        Provides comprehensive family usage statistics, activity metrics,
        and financial information for analytics purposes.
        
        Args:
            family_id: The ID of the family to get statistics for
            
        Returns:
            JSON string containing family statistics
        """
        try:
            user_context = get_mcp_user_context()
            
            # Validate family access (admin required for detailed statistics)
            await require_family_access(family_id, required_role="admin", user_context=user_context)
            
            family_manager = FamilyManager(
                db_manager=db_manager,
                security_manager=security_manager,
                redis_manager=redis_manager
            )
            
            # Get family statistics
            family_stats = await family_manager.get_family_statistics(family_id, user_context.user_id)
            
            # Get SBD account statistics
            sbd_stats = await family_manager.get_family_sbd_statistics(family_id, user_context.user_id)
            
            # Create audit trail
            await create_mcp_audit_trail(
                operation="get_family_statistics_resource",
                user_context=user_context,
                resource_type="family",
                resource_id=family_id,
                metadata={"resource_type": "family_statistics"}
            )
            
            # Compile comprehensive statistics
            statistics = {
                "family_id": family_id,
                "overview": {
                    "total_members": family_stats.get("member_count", 0),
                    "active_members_30d": family_stats.get("active_members_30d", 0),
                    "creation_date": family_stats.get("created_at").isoformat() if family_stats.get("created_at") else None,
                    "days_active": family_stats.get("days_active", 0)
                },
                "activity": {
                    "total_invitations_sent": family_stats.get("invitations_sent", 0),
                    "successful_invitations": family_stats.get("successful_invitations", 0),
                    "pending_invitations": family_stats.get("pending_invitations", 0),
                    "member_joins_30d": family_stats.get("member_joins_30d", 0),
                    "admin_actions_30d": family_stats.get("admin_actions_30d", 0)
                },
                "financial": {
                    "sbd_balance": sbd_stats.get("current_balance", 0),
                    "total_earned": sbd_stats.get("total_earned", 0),
                    "total_spent": sbd_stats.get("total_spent", 0),
                    "pending_requests": sbd_stats.get("pending_requests", 0),
                    "approved_requests_30d": sbd_stats.get("approved_requests_30d", 0),
                    "spending_by_category": sbd_stats.get("spending_by_category", {})
                },
                "permissions": {
                    "members_with_spending": family_stats.get("members_with_spending_permissions", 0),
                    "admin_count": family_stats.get("admin_count", 0),
                    "backup_admins": family_stats.get("backup_admin_count", 0)
                },
                "generated_at": datetime.utcnow().isoformat()
            }
            
            logger.info("Provided family statistics resource for family %s to user %s", 
                       family_id, user_context.user_id)
            
            return json.dumps(statistics, indent=2, default=str)
            
        except Exception as e:
            logger.error("Failed to get family statistics resource for %s: %s", family_id, e)
            return json.dumps({"error": f"Failed to retrieve family statistics: {str(e)}"}, indent=2)

    else:
    logger.warning("FastMCP not available - family resources will not be registered")