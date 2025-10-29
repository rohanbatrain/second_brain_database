"""
MCP Integration for AI Agent Orchestration

Provides integration layer between AI agents and existing MCP tools and resources.
Handles secure execution of MCP operations with proper context management.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
import re

from ....managers.logging_manager import get_logger
from ....config import settings
from ....integrations.mcp.context import MCPUserContext, get_mcp_user_context
from ....integrations.mcp.exceptions import MCPToolError, MCPAuthorizationError, MCPValidationError

logger = get_logger(prefix="[AI_MCPIntegration]")

class MCPToolExecutor:
    """
    Executes MCP tools with proper security and context management.
    
    This class provides a secure interface for AI agents to execute
    existing MCP tools while maintaining proper authentication,
    authorization, and audit logging.
    """
    
    def __init__(self):
        """Initialize the MCP tool executor."""
        self.execution_timeout = getattr(settings, 'MCP_TOOL_TIMEOUT', 30)
        self.max_retries = getattr(settings, 'MCP_TOOL_MAX_RETRIES', 2)
        
        logger.info("MCP tool executor initialized")
    
    async def execute_family_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user_context: MCPUserContext
    ) -> Any:
        """
        Execute a family management tool.
        
        Args:
            tool_name: Name of the family tool to execute
            parameters: Parameters for the tool
            user_context: User context for authentication
            
        Returns:
            Tool execution result
        """
        try:
            # Import family tools module
            from ....integrations.mcp.tools import family_tools
            
            # Get the tool function
            tool_function = getattr(family_tools, tool_name, None)
            if not tool_function:
                raise MCPValidationError(f"Family tool '{tool_name}' not found")
            
            # Execute with timeout
            result = await asyncio.wait_for(
                tool_function(**parameters),
                timeout=self.execution_timeout
            )
            
            logger.debug("Executed family tool '%s' successfully", tool_name)
            return result
            
        except asyncio.TimeoutError:
            raise MCPToolError(f"Family tool '{tool_name}' execution timed out")
        except Exception as e:
            logger.error("Failed to execute family tool '%s': %s", tool_name, e)
            raise MCPToolError(f"Family tool execution failed: {str(e)}")
    
    async def execute_auth_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user_context: MCPUserContext
    ) -> Any:
        """
        Execute an authentication/profile management tool.
        
        Args:
            tool_name: Name of the auth tool to execute
            parameters: Parameters for the tool
            user_context: User context for authentication
            
        Returns:
            Tool execution result
        """
        try:
            # Import auth tools module
            from ....integrations.mcp.tools import auth_tools
            
            # Get the tool function
            tool_function = getattr(auth_tools, tool_name, None)
            if not tool_function:
                raise MCPValidationError(f"Auth tool '{tool_name}' not found")
            
            # Execute with timeout
            result = await asyncio.wait_for(
                tool_function(**parameters),
                timeout=self.execution_timeout
            )
            
            logger.debug("Executed auth tool '%s' successfully", tool_name)
            return result
            
        except asyncio.TimeoutError:
            raise MCPToolError(f"Auth tool '{tool_name}' execution timed out")
        except Exception as e:
            logger.error("Failed to execute auth tool '%s': %s", tool_name, e)
            raise MCPToolError(f"Auth tool execution failed: {str(e)}")
    
    async def execute_shop_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user_context: MCPUserContext
    ) -> Any:
        """
        Execute a shop/commerce tool.
        
        Args:
            tool_name: Name of the shop tool to execute
            parameters: Parameters for the tool
            user_context: User context for authentication
            
        Returns:
            Tool execution result
        """
        try:
            # Import shop tools module
            from ....integrations.mcp.tools import shop_tools
            
            # Get the tool function
            tool_function = getattr(shop_tools, tool_name, None)
            if not tool_function:
                raise MCPValidationError(f"Shop tool '{tool_name}' not found")
            
            # Execute with timeout
            result = await asyncio.wait_for(
                tool_function(**parameters),
                timeout=self.execution_timeout
            )
            
            logger.debug("Executed shop tool '%s' successfully", tool_name)
            return result
            
        except asyncio.TimeoutError:
            raise MCPToolError(f"Shop tool '{tool_name}' execution timed out")
        except Exception as e:
            logger.error("Failed to execute shop tool '%s': %s", tool_name, e)
            raise MCPToolError(f"Shop tool execution failed: {str(e)}")
    
    async def execute_workspace_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user_context: MCPUserContext
    ) -> Any:
        """
        Execute a workspace management tool.
        
        Args:
            tool_name: Name of the workspace tool to execute
            parameters: Parameters for the tool
            user_context: User context for authentication
            
        Returns:
            Tool execution result
        """
        try:
            # Import workspace tools module
            from ....integrations.mcp.tools import workspace_tools
            
            # Get the tool function
            tool_function = getattr(workspace_tools, tool_name, None)
            if not tool_function:
                raise MCPValidationError(f"Workspace tool '{tool_name}' not found")
            
            # Execute with timeout
            result = await asyncio.wait_for(
                tool_function(**parameters),
                timeout=self.execution_timeout
            )
            
            logger.debug("Executed workspace tool '%s' successfully", tool_name)
            return result
            
        except asyncio.TimeoutError:
            raise MCPToolError(f"Workspace tool '{tool_name}' execution timed out")
        except Exception as e:
            logger.error("Failed to execute workspace tool '%s': %s", tool_name, e)
            raise MCPToolError(f"Workspace tool execution failed: {str(e)}")
    
    async def execute_admin_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user_context: MCPUserContext
    ) -> Any:
        """
        Execute an admin/security tool.
        
        Args:
            tool_name: Name of the admin tool to execute
            parameters: Parameters for the tool
            user_context: User context for authentication
            
        Returns:
            Tool execution result
        """
        try:
            # Import admin tools module
            from ....integrations.mcp.tools import admin_tools
            
            # Get the tool function
            tool_function = getattr(admin_tools, tool_name, None)
            if not tool_function:
                raise MCPValidationError(f"Admin tool '{tool_name}' not found")
            
            # Execute with timeout
            result = await asyncio.wait_for(
                tool_function(**parameters),
                timeout=self.execution_timeout
            )
            
            logger.debug("Executed admin tool '%s' successfully", tool_name)
            return result
            
        except asyncio.TimeoutError:
            raise MCPToolError(f"Admin tool '{tool_name}' execution timed out")
        except Exception as e:
            logger.error("Failed to execute admin tool '%s': %s", tool_name, e)
            raise MCPToolError(f"Admin tool execution failed: {str(e)}")

class MCPResourceLoader:
    """
    Loads MCP resources with proper security and context management.
    
    This class provides a secure interface for AI agents to load
    existing MCP resources while maintaining proper authentication
    and authorization.
    """
    
    def __init__(self):
        """Initialize the MCP resource loader."""
        self.load_timeout = getattr(settings, 'MCP_RESOURCE_TIMEOUT', 10)
        
        logger.info("MCP resource loader initialized")
    
    async def load_resource(
        self,
        resource_uri: str,
        user_context: MCPUserContext
    ) -> str:
        """
        Load an MCP resource by URI.
        
        Args:
            resource_uri: URI of the resource to load
            user_context: User context for authentication
            
        Returns:
            Resource content as string
            
        Raises:
            MCPValidationError: If resource URI is invalid
            MCPAuthorizationError: If user lacks access to resource
            MCPToolError: If resource loading fails
        """
        try:
            # Parse resource URI
            resource_info = self._parse_resource_uri(resource_uri)
            
            # Route to appropriate resource loader
            if resource_info["scheme"] == "family":
                return await self._load_family_resource(resource_info, user_context)
            elif resource_info["scheme"] == "user":
                return await self._load_user_resource(resource_info, user_context)
            elif resource_info["scheme"] == "shop":
                return await self._load_shop_resource(resource_info, user_context)
            elif resource_info["scheme"] == "workspace":
                return await self._load_workspace_resource(resource_info, user_context)
            else:
                raise MCPValidationError(f"Unsupported resource scheme: {resource_info['scheme']}")
            
        except Exception as e:
            logger.error("Failed to load resource '%s': %s", resource_uri, e)
            if isinstance(e, (MCPValidationError, MCPAuthorizationError, MCPToolError)):
                raise
            else:
                raise MCPToolError(f"Resource loading failed: {str(e)}")
    
    def _parse_resource_uri(self, resource_uri: str) -> Dict[str, Any]:
        """
        Parse a resource URI into components.
        
        Args:
            resource_uri: URI to parse (e.g., "family://123/info")
            
        Returns:
            Dictionary containing parsed URI components
        """
        try:
            # Basic URI parsing
            if "://" not in resource_uri:
                raise MCPValidationError("Invalid resource URI format")
            
            scheme, path = resource_uri.split("://", 1)
            
            # Parse path components
            path_parts = path.split("/")
            
            return {
                "scheme": scheme,
                "path": path,
                "path_parts": path_parts,
                "full_uri": resource_uri
            }
            
        except Exception as e:
            raise MCPValidationError(f"Failed to parse resource URI: {str(e)}")
    
    async def _load_family_resource(
        self,
        resource_info: Dict[str, Any],
        user_context: MCPUserContext
    ) -> str:
        """Load a family resource."""
        try:
            from ....integrations.mcp.resources import family_resources
            
            path_parts = resource_info["path_parts"]
            
            if len(path_parts) >= 2:
                family_id = path_parts[0]
                resource_type = path_parts[1]
                
                if resource_type == "info":
                    return await family_resources.get_family_info_resource(family_id)
                elif resource_type == "members":
                    return await family_resources.get_family_members_resource(family_id)
                elif resource_type == "statistics":
                    return await family_resources.get_family_statistics_resource(family_id)
            
            raise MCPValidationError(f"Invalid family resource path: {resource_info['path']}")
            
        except Exception as e:
            if isinstance(e, (MCPValidationError, MCPAuthorizationError)):
                raise
            else:
                raise MCPToolError(f"Failed to load family resource: {str(e)}")
    
    async def _load_user_resource(
        self,
        resource_info: Dict[str, Any],
        user_context: MCPUserContext
    ) -> str:
        """Load a user resource."""
        try:
            from ....integrations.mcp.resources import user_resources, shop_resources
            
            path_parts = resource_info["path_parts"]
            
            if len(path_parts) >= 2:
                user_id = path_parts[0]
                resource_type = path_parts[1]
                
                if resource_type == "profile":
                    return await user_resources.get_user_profile_resource(user_id)
                elif resource_type == "preferences":
                    return await user_resources.get_user_preferences_resource(user_id)
                elif resource_type == "activity":
                    return await user_resources.get_user_activity_resource(user_id)
                elif resource_type == "assets":
                    return await shop_resources.get_user_assets_resource(user_id)
                elif resource_type == "transactions":
                    return await shop_resources.get_transaction_history_resource(user_id)
                elif len(path_parts) >= 3:
                    # Handle nested resources like user://123/sbd/balance
                    sub_resource = path_parts[2]
                    if resource_type == "sbd" and sub_resource == "balance":
                        return await shop_resources.get_sbd_balance_resource(user_id)
                    elif resource_type == "spending" and sub_resource == "analytics":
                        return await shop_resources.get_spending_analytics_resource(user_id)
                    elif resource_type == "assets" and sub_resource == "usage":
                        return await shop_resources.get_asset_usage_resource(user_id)
            
            raise MCPValidationError(f"Invalid user resource path: {resource_info['path']}")
            
        except Exception as e:
            if isinstance(e, (MCPValidationError, MCPAuthorizationError)):
                raise
            else:
                raise MCPToolError(f"Failed to load user resource: {str(e)}")
    
    async def _load_shop_resource(
        self,
        resource_info: Dict[str, Any],
        user_context: MCPUserContext
    ) -> str:
        """Load a shop resource."""
        try:
            from ....integrations.mcp.resources import shop_resources
            
            path_parts = resource_info["path_parts"]
            
            if len(path_parts) >= 1:
                resource_type = path_parts[0]
                
                if resource_type == "catalog":
                    return await shop_resources.get_shop_catalog_resource()
            
            raise MCPValidationError(f"Invalid shop resource path: {resource_info['path']}")
            
        except Exception as e:
            if isinstance(e, (MCPValidationError, MCPAuthorizationError)):
                raise
            else:
                raise MCPToolError(f"Failed to load shop resource: {str(e)}")
    
    async def _load_workspace_resource(
        self,
        resource_info: Dict[str, Any],
        user_context: MCPUserContext
    ) -> str:
        """Load a workspace resource."""
        try:
            from ....integrations.mcp.resources import workspace_resources
            
            path_parts = resource_info["path_parts"]
            
            if len(path_parts) >= 2:
                workspace_id = path_parts[0]
                resource_type = path_parts[1]
                
                # Workspace resources would be implemented here
                # For now, return a placeholder
                return json.dumps({
                    "workspace_id": workspace_id,
                    "resource_type": resource_type,
                    "message": "Workspace resources not yet implemented"
                })
            
            raise MCPValidationError(f"Invalid workspace resource path: {resource_info['path']}")
            
        except Exception as e:
            if isinstance(e, (MCPValidationError, MCPAuthorizationError)):
                raise
            else:
                raise MCPToolError(f"Failed to load workspace resource: {str(e)}")

class MCPContextManager:
    """
    Manages MCP context for AI agent operations.
    
    This class handles the setup and cleanup of MCP context variables
    to ensure proper authentication and authorization for tool executions.
    """
    
    def __init__(self):
        """Initialize the MCP context manager."""
        logger.info("MCP context manager initialized")
    
    async def create_user_context_from_session(
        self,
        session_context: Dict[str, Any]
    ) -> MCPUserContext:
        """
        Create MCP user context from AI session context.
        
        Args:
            session_context: AI session context containing user information
            
        Returns:
            MCPUserContext for MCP operations
        """
        try:
            # Extract user information from session context
            user_id = session_context.get("user_id")
            if not user_id:
                raise MCPValidationError("User ID not found in session context")
            
            # Get user data from database
            from ....database import db_manager
            users_collection = db_manager.get_collection("users")
            
            user_doc = await users_collection.find_one({"_id": user_id})
            if not user_doc:
                raise MCPValidationError(f"User not found: {user_id}")
            
            # Create MCP user context
            from ..context import create_mcp_user_context_from_fastapi_user
            
            mcp_context = await create_mcp_user_context_from_fastapi_user(
                fastapi_user=user_doc,
                ip_address=session_context.get("ip_address"),
                user_agent=session_context.get("user_agent"),
                token_type="ai_session",
                token_id=session_context.get("session_id")
            )
            
            logger.debug("Created MCP user context for AI session: %s", user_id)
            return mcp_context
            
        except Exception as e:
            logger.error("Failed to create MCP user context from session: %s", e)
            raise MCPToolError(f"Failed to create user context: {str(e)}")
    
    async def validate_context_permissions(
        self,
        user_context: MCPUserContext,
        required_permissions: List[str]
    ) -> bool:
        """
        Validate that user context has required permissions.
        
        Args:
            user_context: MCP user context to validate
            required_permissions: List of required permissions
            
        Returns:
            True if user has all required permissions
        """
        try:
            if not required_permissions:
                return True
            
            return user_context.has_all_permissions(required_permissions)
            
        except Exception as e:
            logger.error("Failed to validate context permissions: %s", e)
            return False
    
    async def enrich_context_with_family_data(
        self,
        user_context: MCPUserContext
    ) -> MCPUserContext:
        """
        Enrich user context with family membership data.
        
        Args:
            user_context: MCP user context to enrich
            
        Returns:
            Enriched MCP user context
        """
        try:
            # Get family memberships from database
            from ....database import db_manager
            families_collection = db_manager.get_collection("families")
            
            family_memberships = await families_collection.find({
                "members.user_id": user_context.user_id
            }).to_list(length=None)
            
            # Update context with family data
            family_data = []
            for family in family_memberships:
                # Find user's role in this family
                user_member = next(
                    (m for m in family.get("members", []) if m.get("user_id") == user_context.user_id),
                    None
                )
                
                if user_member:
                    family_data.append({
                        "family_id": str(family["_id"]),
                        "family_name": family.get("name"),
                        "role": user_member.get("role"),
                        "joined_at": user_member.get("joined_at")
                    })
            
            # Update context
            user_context.family_memberships = family_data
            
            logger.debug("Enriched context with %d family memberships", len(family_data))
            return user_context
            
        except Exception as e:
            logger.warning("Failed to enrich context with family data: %s", e)
            # Return original context if enrichment fails
            return user_context
    
    async def enrich_context_with_workspace_data(
        self,
        user_context: MCPUserContext
    ) -> MCPUserContext:
        """
        Enrich user context with workspace membership data.
        
        Args:
            user_context: MCP user context to enrich
            
        Returns:
            Enriched MCP user context
        """
        try:
            # Get workspace memberships from database
            from ....database import db_manager
            workspaces_collection = db_manager.get_collection("workspaces")
            
            workspace_memberships = await workspaces_collection.find({
                "members.user_id": user_context.user_id
            }).to_list(length=None)
            
            # Update context with workspace data
            workspace_data = []
            for workspace in workspace_memberships:
                # Find user's role in this workspace
                user_member = next(
                    (m for m in workspace.get("members", []) if m.get("user_id") == user_context.user_id),
                    None
                )
                
                if user_member:
                    workspace_data.append({
                        "_id": str(workspace["_id"]),
                        "name": workspace.get("name"),
                        "role": user_member.get("role"),
                        "joined_at": user_member.get("joined_at")
                    })
            
            # Update context
            user_context.workspaces = workspace_data
            
            logger.debug("Enriched context with %d workspace memberships", len(workspace_data))
            return user_context
            
        except Exception as e:
            logger.warning("Failed to enrich context with workspace data: %s", e)
            # Return original context if enrichment fails
            return user_context