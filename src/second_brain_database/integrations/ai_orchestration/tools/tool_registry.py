"""
Tool Registry for AI Agent Orchestration

Manages registration and discovery of MCP tools for AI agents.
Provides mapping between agent types and available tools.
"""

from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum

from ....managers.logging_manager import get_logger

logger = get_logger(prefix="[AI_ToolRegistry]")

class AgentType(Enum):
    """Enumeration of available AI agent types."""
    FAMILY = "family"
    PERSONAL = "personal"
    WORKSPACE = "workspace"
    COMMERCE = "commerce"
    SECURITY = "security"
    VOICE = "voice"

@dataclass
class ToolInfo:
    """Information about a registered tool."""
    name: str
    function: Callable
    category: str
    description: str
    permissions: List[str] = field(default_factory=list)
    rate_limit_action: str = "default"
    agent_types: Set[AgentType] = field(default_factory=set)
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

class ToolRegistry:
    """
    Registry for managing MCP tools available to AI agents.
    
    This class maintains a registry of all available MCP tools and provides
    methods for discovering tools based on agent type, permissions, and categories.
    """
    
    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, ToolInfo] = {}
        self._categories: Dict[str, List[str]] = {}
        self._agent_mappings: Dict[AgentType, Set[str]] = {
            agent_type: set() for agent_type in AgentType
        }
        
        logger.info("Tool registry initialized")
    
    def register_tool(
        self,
        name: str,
        function: Callable,
        category: str,
        description: str = "",
        permissions: Optional[List[str]] = None,
        rate_limit_action: str = "default",
        agent_types: Optional[List[AgentType]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a tool in the registry.
        
        Args:
            name: Unique name of the tool
            function: Callable function that implements the tool
            category: Category of the tool (family, auth, shop, etc.)
            description: Human-readable description of the tool
            permissions: List of required permissions
            rate_limit_action: Rate limiting action identifier
            agent_types: List of agent types that can use this tool
            parameters: Parameter schema for the tool
            metadata: Additional metadata about the tool
        """
        try:
            # Set defaults
            permissions = permissions or []
            agent_types = agent_types or []
            parameters = parameters or {}
            metadata = metadata or {}
            
            # Convert agent types to set
            agent_type_set = set(agent_types) if agent_types else set()
            
            # Create tool info
            tool_info = ToolInfo(
                name=name,
                function=function,
                category=category,
                description=description,
                permissions=permissions,
                rate_limit_action=rate_limit_action,
                agent_types=agent_type_set,
                parameters=parameters,
                metadata=metadata
            )
            
            # Register the tool
            self._tools[name] = tool_info
            
            # Update category mapping
            if category not in self._categories:
                self._categories[category] = []
            if name not in self._categories[category]:
                self._categories[category].append(name)
            
            # Update agent mappings
            for agent_type in agent_type_set:
                self._agent_mappings[agent_type].add(name)
            
            logger.debug("Registered tool '%s' in category '%s'", name, category)
            
        except Exception as e:
            logger.error("Failed to register tool '%s': %s", name, e)
    
    def has_tool(self, name: str) -> bool:
        """
        Check if a tool is registered.
        
        Args:
            name: Name of the tool to check
            
        Returns:
            True if tool is registered, False otherwise
        """
        return name in self._tools
    
    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get tool information by name.
        
        Args:
            name: Name of the tool
            
        Returns:
            Dictionary containing tool information, or None if not found
        """
        if name not in self._tools:
            return None
        
        tool_info = self._tools[name]
        return {
            "name": tool_info.name,
            "function": tool_info.function,
            "category": tool_info.category,
            "description": tool_info.description,
            "permissions": tool_info.permissions,
            "rate_limit_action": tool_info.rate_limit_action,
            "agent_types": list(tool_info.agent_types),
            "parameters": tool_info.parameters,
            "metadata": tool_info.metadata
        }
    
    def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all registered tools.
        
        Returns:
            Dictionary mapping tool names to tool information
        """
        return {name: self.get_tool(name) for name in self._tools.keys()}
    
    def get_tools_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all tools in a specific category.
        
        Args:
            category: Category to filter by
            
        Returns:
            List of tools in the specified category
        """
        if category not in self._categories:
            return []
        
        return [self.get_tool(name) for name in self._categories[category]]
    
    def get_tools_by_agent_type(self, agent_type: AgentType) -> List[Dict[str, Any]]:
        """
        Get all tools available to a specific agent type.
        
        Args:
            agent_type: Agent type to filter by
            
        Returns:
            List of tools available to the agent type
        """
        if agent_type not in self._agent_mappings:
            return []
        
        tool_names = self._agent_mappings[agent_type]
        return [self.get_tool(name) for name in tool_names if self.has_tool(name)]
    
    def get_tools_by_permissions(self, user_permissions: List[str]) -> List[Dict[str, Any]]:
        """
        Get all tools that a user can access based on their permissions.
        
        Args:
            user_permissions: List of user permissions
            
        Returns:
            List of accessible tools
        """
        accessible_tools = []
        
        for tool_name, tool_info in self._tools.items():
            required_permissions = tool_info.permissions
            
            # If no permissions required, tool is accessible
            if not required_permissions:
                accessible_tools.append(self.get_tool(tool_name))
                continue
            
            # Check if user has all required permissions
            if all(perm in user_permissions for perm in required_permissions):
                accessible_tools.append(self.get_tool(tool_name))
        
        return accessible_tools
    
    def get_categories(self) -> List[str]:
        """
        Get all available tool categories.
        
        Returns:
            List of category names
        """
        return list(self._categories.keys())
    
    def search_tools(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        agent_type: Optional[AgentType] = None,
        permissions: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for tools based on various criteria.
        
        Args:
            query: Text query to search in tool names and descriptions
            category: Category to filter by
            agent_type: Agent type to filter by
            permissions: User permissions to filter by
            
        Returns:
            List of matching tools
        """
        results = list(self._tools.values())
        
        # Filter by category
        if category:
            results = [tool for tool in results if tool.category == category]
        
        # Filter by agent type
        if agent_type:
            results = [tool for tool in results if agent_type in tool.agent_types]
        
        # Filter by permissions
        if permissions:
            results = [
                tool for tool in results
                if not tool.permissions or all(perm in permissions for perm in tool.permissions)
            ]
        
        # Filter by text query
        if query:
            query_lower = query.lower()
            results = [
                tool for tool in results
                if query_lower in tool.name.lower() or query_lower in tool.description.lower()
            ]
        
        # Convert to dictionaries
        return [self.get_tool(tool.name) for tool in results]
    
    def get_tool_count(self) -> int:
        """
        Get the total number of registered tools.
        
        Returns:
            Number of registered tools
        """
        return len(self._tools)
    
    def get_category_count(self) -> int:
        """
        Get the total number of categories.
        
        Returns:
            Number of categories
        """
        return len(self._categories)
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the tool registry.
        
        Returns:
            Dictionary containing registry statistics
        """
        stats = {
            "total_tools": self.get_tool_count(),
            "total_categories": self.get_category_count(),
            "categories": {
                category: len(tools) 
                for category, tools in self._categories.items()
            },
            "agent_mappings": {
                agent_type.value: len(tools)
                for agent_type, tools in self._agent_mappings.items()
            }
        }
        
        return stats

class AgentToolMapping:
    """
    Manages the mapping between agent types and their available tools.
    
    This class defines which tools each agent type can access and provides
    methods for configuring agent-specific tool access.
    """
    
    # Default tool mappings for each agent type
    DEFAULT_MAPPINGS = {
        AgentType.FAMILY: {
            "categories": ["family"],
            "specific_tools": [
                "get_family_info",
                "get_family_members", 
                "create_family",
                "add_family_member",
                "remove_family_member",
                "update_family_settings",
                "get_family_relationships",
                "update_relationship"
            ]
        },
        AgentType.PERSONAL: {
            "categories": ["auth"],
            "specific_tools": [
                "get_user_profile",
                "update_user_profile",
                "get_user_preferences",
                "update_user_preferences",
                "get_user_avatar",
                "get_user_banner",
                "set_current_avatar",
                "set_current_banner",
                "get_auth_status"
            ]
        },
        AgentType.WORKSPACE: {
            "categories": ["workspace"],
            "specific_tools": [
                # Workspace tools would be defined here
                # These would come from workspace_tools.py
            ]
        },
        AgentType.COMMERCE: {
            "categories": ["shop"],
            "specific_tools": [
                "list_shop_items",
                "get_item_details_tool",
                "search_shop_items",
                "get_shop_categories",
                "get_featured_items",
                "get_new_arrivals",
                "purchase_item"
            ]
        },
        AgentType.SECURITY: {
            "categories": ["admin"],
            "specific_tools": [
                # Admin/security tools would be defined here
                # These would come from admin_tools.py
            ]
        },
        AgentType.VOICE: {
            "categories": ["family", "auth", "shop", "workspace"],
            "specific_tools": [
                # Voice agent can access tools from multiple categories
                # for voice command processing
            ]
        }
    }
    
    def __init__(self, tool_registry: ToolRegistry):
        """
        Initialize agent tool mapping.
        
        Args:
            tool_registry: Tool registry instance to work with
        """
        self.tool_registry = tool_registry
        self._custom_mappings: Dict[AgentType, Dict[str, Any]] = {}
        
        logger.info("Agent tool mapping initialized")
    
    def apply_default_mappings(self) -> None:
        """Apply default tool mappings to the registry."""
        try:
            for agent_type, mapping in self.DEFAULT_MAPPINGS.items():
                # Get tools by categories
                category_tools = []
                for category in mapping.get("categories", []):
                    category_tools.extend(self.tool_registry.get_tools_by_category(category))
                
                # Get specific tools
                specific_tools = mapping.get("specific_tools", [])
                
                # Update registry with agent type mappings
                for tool in category_tools:
                    if self.tool_registry.has_tool(tool["name"]):
                        tool_info = self.tool_registry._tools[tool["name"]]
                        tool_info.agent_types.add(agent_type)
                
                for tool_name in specific_tools:
                    if self.tool_registry.has_tool(tool_name):
                        tool_info = self.tool_registry._tools[tool_name]
                        tool_info.agent_types.add(agent_type)
                
                # Update agent mappings in registry
                self.tool_registry._agent_mappings[agent_type].update(
                    tool["name"] for tool in category_tools
                )
                self.tool_registry._agent_mappings[agent_type].update(specific_tools)
            
            logger.info("Applied default agent tool mappings")
            
        except Exception as e:
            logger.error("Failed to apply default mappings: %s", e)
    
    def add_tool_to_agent(self, agent_type: AgentType, tool_name: str) -> bool:
        """
        Add a tool to an agent's available tools.
        
        Args:
            agent_type: Agent type to add tool to
            tool_name: Name of the tool to add
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.tool_registry.has_tool(tool_name):
                logger.warning("Tool '%s' not found in registry", tool_name)
                return False
            
            # Update tool info
            tool_info = self.tool_registry._tools[tool_name]
            tool_info.agent_types.add(agent_type)
            
            # Update agent mapping
            self.tool_registry._agent_mappings[agent_type].add(tool_name)
            
            logger.debug("Added tool '%s' to agent type '%s'", tool_name, agent_type.value)
            return True
            
        except Exception as e:
            logger.error("Failed to add tool '%s' to agent '%s': %s", 
                        tool_name, agent_type.value, e)
            return False
    
    def remove_tool_from_agent(self, agent_type: AgentType, tool_name: str) -> bool:
        """
        Remove a tool from an agent's available tools.
        
        Args:
            agent_type: Agent type to remove tool from
            tool_name: Name of the tool to remove
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.tool_registry.has_tool(tool_name):
                return False
            
            # Update tool info
            tool_info = self.tool_registry._tools[tool_name]
            tool_info.agent_types.discard(agent_type)
            
            # Update agent mapping
            self.tool_registry._agent_mappings[agent_type].discard(tool_name)
            
            logger.debug("Removed tool '%s' from agent type '%s'", tool_name, agent_type.value)
            return True
            
        except Exception as e:
            logger.error("Failed to remove tool '%s' from agent '%s': %s", 
                        tool_name, agent_type.value, e)
            return False
    
    def get_agent_tools(self, agent_type: AgentType) -> List[str]:
        """
        Get all tools available to a specific agent type.
        
        Args:
            agent_type: Agent type to get tools for
            
        Returns:
            List of tool names available to the agent
        """
        return list(self.tool_registry._agent_mappings.get(agent_type, set()))
    
    def can_agent_use_tool(self, agent_type: AgentType, tool_name: str) -> bool:
        """
        Check if an agent type can use a specific tool.
        
        Args:
            agent_type: Agent type to check
            tool_name: Tool name to check
            
        Returns:
            True if agent can use the tool, False otherwise
        """
        return tool_name in self.tool_registry._agent_mappings.get(agent_type, set())