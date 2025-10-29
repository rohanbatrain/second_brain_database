"""
Tool Coordinator for AI Agent Orchestration

Manages MCP tool execution with security and performance optimization.
Provides a unified interface for AI agents to execute existing MCP tools
with proper authentication, rate limiting, and audit logging.
"""

import asyncio
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timezone
import json
import inspect
from dataclasses import dataclass

from ....managers.logging_manager import get_logger
from ....config import settings
from ....integrations.mcp.context import (
    MCPUserContext, MCPRequestContext, 
    set_mcp_user_context, set_mcp_request_context, clear_mcp_context,
    create_mcp_request_context, log_mcp_operation
)
from ....integrations.mcp.exceptions import MCPToolError, MCPAuthorizationError, MCPValidationError
from .tool_registry import ToolRegistry
from .mcp_integration import MCPToolExecutor, MCPResourceLoader

logger = get_logger(prefix="[AI_ToolCoordinator]")

@dataclass
class ToolExecutionResult:
    """Result of tool execution with metadata."""
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time_ms: float = 0
    tool_name: str = ""
    parameters: Dict[str, Any] = None
    metadata: Dict[str, Any] = None

class ToolCoordinator:
    """
    Manages MCP tool execution with security and performance optimization.
    
    This class provides the main interface for AI agents to execute MCP tools
    while ensuring proper authentication, authorization, rate limiting, and
    audit logging.
    """
    
    def __init__(self):
        """Initialize the tool coordinator with required components."""
        self.tool_registry = ToolRegistry()
        self.mcp_executor = MCPToolExecutor()
        self.resource_loader = MCPResourceLoader()
        self.execution_cache: Dict[str, Any] = {}
        self.performance_metrics: Dict[str, List[float]] = {}
        
        # Initialize tool registry with existing MCP tools
        self._initialize_tool_registry()
        
        logger.info("Tool coordinator initialized with %d registered tools", 
                   len(self.tool_registry.get_all_tools()))
    
    def _initialize_tool_registry(self) -> None:
        """Initialize the tool registry with existing MCP tools."""
        registered_modules = []
        
        # Try to register family tools
        try:
            from ....integrations.mcp.tools import family_tools
            self._register_module_tools(family_tools, "family")
            registered_modules.append("family")
        except Exception as e:
            logger.warning("Failed to register family tools: %s", e)
        
        # Try to register auth tools
        try:
            from ....integrations.mcp.tools import auth_tools
            self._register_module_tools(auth_tools, "auth")
            registered_modules.append("auth")
        except Exception as e:
            logger.warning("Failed to register auth tools: %s", e)
        
        # Try to register shop tools
        try:
            from ....integrations.mcp.tools import shop_tools
            self._register_module_tools(shop_tools, "shop")
            registered_modules.append("shop")
        except Exception as e:
            logger.warning("Failed to register shop tools: %s", e)
        
        # Try to register workspace tools
        try:
            from ....integrations.mcp.tools import workspace_tools
            self._register_module_tools(workspace_tools, "workspace")
            registered_modules.append("workspace")
        except Exception as e:
            logger.warning("Failed to register workspace tools: %s", e)
        
        # Try to register admin tools
        try:
            from ....integrations.mcp.tools import admin_tools
            self._register_module_tools(admin_tools, "admin")
            registered_modules.append("admin")
        except Exception as e:
            logger.warning("Failed to register admin tools: %s", e)
        
        if registered_modules:
            logger.info("Successfully registered MCP tools from modules: %s", registered_modules)
        else:
            logger.warning("No MCP tool modules were successfully registered")
    
    def _register_module_tools(self, module: Any, category: str) -> None:
        """Register all tools from a module with the tool registry."""
        try:
            # Get all functions that are decorated as MCP tools
            for name in dir(module):
                try:
                    obj = getattr(module, name)
                    # Check for authenticated_tool decorated functions
                    if callable(obj) and hasattr(obj, '_mcp_tool_name'):
                        # This is an MCP tool function decorated with @authenticated_tool
                        tool_name = getattr(obj, '_mcp_tool_name', name)
                        description = getattr(obj, '_mcp_tool_description', '')
                        permissions = getattr(obj, '_mcp_tool_permissions', [])
                        rate_limit_action = getattr(obj, '_mcp_rate_limit_action', 'default')
                        
                        self.tool_registry.register_tool(
                            name=tool_name,
                            function=obj,
                            category=category,
                            description=description,
                            permissions=permissions,
                            rate_limit_action=rate_limit_action
                        )
                        logger.debug("Registered MCP tool: %s", tool_name)
                except Exception as attr_error:
                    # Skip objects that can't be accessed (like imports that failed)
                    logger.debug("Skipped object %s in %s module: %s", name, category, attr_error)
                    continue
                    
            logger.debug("Registered tools from %s module", category)
            
        except Exception as e:
            logger.warning("Failed to register tools from %s module: %s", category, e)
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user_context: MCPUserContext,
        session_id: Optional[str] = None
    ) -> ToolExecutionResult:
        """
        Execute an MCP tool with proper security and context management.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters to pass to the tool
            user_context: User context for authentication and authorization
            session_id: Optional session ID for tracking
            
        Returns:
            ToolExecutionResult with execution details and result
            
        Raises:
            MCPToolError: If tool execution fails
            MCPAuthorizationError: If user lacks required permissions
            MCPValidationError: If parameters are invalid
        """
        start_time = datetime.now(timezone.utc)
        request_context = None
        
        try:
            # Create request context for this execution
            request_context = create_mcp_request_context(
                operation_type="tool",
                tool_name=tool_name,
                parameters=parameters
            )
            
            # Set contexts for MCP operations
            set_mcp_user_context(user_context)
            set_mcp_request_context(request_context)
            
            # Validate tool exists
            if not self.tool_registry.has_tool(tool_name):
                raise MCPValidationError(f"Tool '{tool_name}' not found")
            
            # Get tool information
            tool_info = self.tool_registry.get_tool(tool_name)
            
            # Validate user permissions
            required_permissions = tool_info.get('permissions', [])
            if required_permissions:
                if not user_context.has_all_permissions(required_permissions):
                    raise MCPAuthorizationError(
                        f"Insufficient permissions for tool '{tool_name}'",
                        required_permissions=required_permissions,
                        user_permissions=user_context.permissions
                    )
            
            # Execute the tool
            tool_function = tool_info['function']
            
            # Prepare parameters for execution
            execution_params = self._prepare_tool_parameters(tool_function, parameters)
            
            # Execute with timeout
            execution_timeout = getattr(settings, 'MCP_TOOL_TIMEOUT', 30)
            result = await asyncio.wait_for(
                tool_function(**execution_params),
                timeout=execution_timeout
            )
            
            # Calculate execution time
            end_time = datetime.now(timezone.utc)
            execution_time_ms = (end_time - start_time).total_seconds() * 1000
            
            # Update performance metrics
            self._update_performance_metrics(tool_name, execution_time_ms)
            
            # Mark request as completed
            if request_context:
                request_context.mark_completed()
            
            # Log successful execution
            await log_mcp_operation(
                operation_name=f"execute_tool:{tool_name}",
                success=True,
                additional_context={
                    "execution_time_ms": execution_time_ms,
                    "parameters_count": len(parameters),
                    "session_id": session_id
                }
            )
            
            logger.info(
                "Successfully executed tool '%s' for user %s in %.2fms",
                tool_name, user_context.user_id, execution_time_ms
            )
            
            return ToolExecutionResult(
                success=True,
                result=result,
                execution_time_ms=execution_time_ms,
                tool_name=tool_name,
                parameters=parameters,
                metadata={
                    "session_id": session_id,
                    "permissions_checked": required_permissions,
                    "user_id": user_context.user_id
                }
            )
            
        except asyncio.TimeoutError:
            error_msg = f"Tool '{tool_name}' execution timed out"
            logger.error(error_msg)
            
            if request_context:
                request_context.mark_completed(error=TimeoutError(error_msg))
            
            await log_mcp_operation(
                operation_name=f"execute_tool:{tool_name}",
                success=False,
                error=TimeoutError(error_msg)
            )
            
            return ToolExecutionResult(
                success=False,
                error=error_msg,
                tool_name=tool_name,
                parameters=parameters
            )
            
        except (MCPToolError, MCPAuthorizationError, MCPValidationError) as e:
            # These are expected MCP errors
            logger.warning("Tool execution failed: %s", e)
            
            if request_context:
                request_context.mark_completed(error=e)
            
            await log_mcp_operation(
                operation_name=f"execute_tool:{tool_name}",
                success=False,
                error=e
            )
            
            return ToolExecutionResult(
                success=False,
                error=str(e),
                tool_name=tool_name,
                parameters=parameters
            )
            
        except Exception as e:
            # Unexpected errors
            error_msg = f"Unexpected error executing tool '{tool_name}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            if request_context:
                request_context.mark_completed(error=e)
            
            await log_mcp_operation(
                operation_name=f"execute_tool:{tool_name}",
                success=False,
                error=e
            )
            
            return ToolExecutionResult(
                success=False,
                error=error_msg,
                tool_name=tool_name,
                parameters=parameters
            )
            
        finally:
            # Always clear MCP context
            clear_mcp_context()
    
    def _prepare_tool_parameters(self, tool_function: Callable, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare parameters for tool execution by matching function signature.
        
        Args:
            tool_function: The tool function to execute
            parameters: Raw parameters from the agent
            
        Returns:
            Dictionary of parameters matching the function signature
        """
        try:
            # Get function signature
            sig = inspect.signature(tool_function)
            
            # Prepare parameters matching the signature
            execution_params = {}
            
            for param_name, param in sig.parameters.items():
                if param_name in parameters:
                    execution_params[param_name] = parameters[param_name]
                elif param.default is not inspect.Parameter.empty:
                    # Use default value if available
                    execution_params[param_name] = param.default
                elif param.kind != inspect.Parameter.VAR_KEYWORD:
                    # Required parameter is missing
                    logger.warning("Missing required parameter '%s' for tool function", param_name)
            
            return execution_params
            
        except Exception as e:
            logger.error("Failed to prepare tool parameters: %s", e)
            # Return original parameters as fallback
            return parameters
    
    def _update_performance_metrics(self, tool_name: str, execution_time_ms: float) -> None:
        """Update performance metrics for a tool."""
        if tool_name not in self.performance_metrics:
            self.performance_metrics[tool_name] = []
        
        # Keep only last 100 measurements
        metrics = self.performance_metrics[tool_name]
        metrics.append(execution_time_ms)
        if len(metrics) > 100:
            metrics.pop(0)
    
    async def load_resource(
        self,
        resource_uri: str,
        user_context: MCPUserContext,
        session_id: Optional[str] = None
    ) -> ToolExecutionResult:
        """
        Load an MCP resource with proper security and context management.
        
        Args:
            resource_uri: URI of the resource to load
            user_context: User context for authentication and authorization
            session_id: Optional session ID for tracking
            
        Returns:
            ToolExecutionResult with resource data
        """
        start_time = datetime.now(timezone.utc)
        request_context = None
        
        try:
            # Create request context for this operation
            request_context = create_mcp_request_context(
                operation_type="resource",
                resource_uri=resource_uri
            )
            
            # Set contexts for MCP operations
            set_mcp_user_context(user_context)
            set_mcp_request_context(request_context)
            
            # Load resource using MCP resource loader
            result = await self.resource_loader.load_resource(resource_uri, user_context)
            
            # Calculate execution time
            end_time = datetime.now(timezone.utc)
            execution_time_ms = (end_time - start_time).total_seconds() * 1000
            
            # Mark request as completed
            if request_context:
                request_context.mark_completed()
            
            # Log successful operation
            await log_mcp_operation(
                operation_name=f"load_resource:{resource_uri}",
                success=True,
                additional_context={
                    "execution_time_ms": execution_time_ms,
                    "session_id": session_id
                }
            )
            
            logger.info(
                "Successfully loaded resource '%s' for user %s in %.2fms",
                resource_uri, user_context.user_id, execution_time_ms
            )
            
            return ToolExecutionResult(
                success=True,
                result=result,
                execution_time_ms=execution_time_ms,
                tool_name=f"resource:{resource_uri}",
                metadata={
                    "session_id": session_id,
                    "resource_uri": resource_uri,
                    "user_id": user_context.user_id
                }
            )
            
        except Exception as e:
            error_msg = f"Failed to load resource '{resource_uri}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            if request_context:
                request_context.mark_completed(error=e)
            
            await log_mcp_operation(
                operation_name=f"load_resource:{resource_uri}",
                success=False,
                error=e
            )
            
            return ToolExecutionResult(
                success=False,
                error=error_msg,
                tool_name=f"resource:{resource_uri}",
                metadata={"resource_uri": resource_uri}
            )
            
        finally:
            # Always clear MCP context
            clear_mcp_context()
    
    async def list_available_tools(self, user_context: MCPUserContext) -> List[Dict[str, Any]]:
        """
        List all tools available to the current user based on their permissions.
        
        Args:
            user_context: User context for permission checking
            
        Returns:
            List of available tools with metadata
        """
        try:
            all_tools = self.tool_registry.get_all_tools()
            available_tools = []
            
            for tool_name, tool_info in all_tools.items():
                # Check if user has required permissions
                required_permissions = tool_info.get('permissions', [])
                
                if not required_permissions or user_context.has_all_permissions(required_permissions):
                    # Get performance metrics if available
                    metrics = self.performance_metrics.get(tool_name, [])
                    avg_time = sum(metrics) / len(metrics) if metrics else 0
                    
                    available_tools.append({
                        "name": tool_name,
                        "category": tool_info.get('category', 'unknown'),
                        "description": tool_info.get('description', ''),
                        "permissions": required_permissions,
                        "rate_limit_action": tool_info.get('rate_limit_action', 'default'),
                        "performance": {
                            "avg_execution_time_ms": round(avg_time, 2),
                            "execution_count": len(metrics)
                        }
                    })
            
            logger.info("Listed %d available tools for user %s", 
                       len(available_tools), user_context.user_id)
            
            return available_tools
            
        except Exception as e:
            logger.error("Failed to list available tools: %s", e)
            return []
    
    async def validate_tool_access(
        self,
        tool_name: str,
        user_context: MCPUserContext
    ) -> bool:
        """
        Validate that a user has access to execute a specific tool.
        
        Args:
            tool_name: Name of the tool to check
            user_context: User context for permission checking
            
        Returns:
            True if user can execute the tool, False otherwise
        """
        try:
            if not self.tool_registry.has_tool(tool_name):
                return False
            
            tool_info = self.tool_registry.get_tool(tool_name)
            required_permissions = tool_info.get('permissions', [])
            
            if not required_permissions:
                return True
            
            return user_context.has_all_permissions(required_permissions)
            
        except Exception as e:
            logger.error("Failed to validate tool access for %s: %s", tool_name, e)
            return False
    
    def get_tool_performance_metrics(self, tool_name: str) -> Dict[str, Any]:
        """
        Get performance metrics for a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Dictionary containing performance metrics
        """
        metrics = self.performance_metrics.get(tool_name, [])
        
        if not metrics:
            return {
                "execution_count": 0,
                "avg_execution_time_ms": 0,
                "min_execution_time_ms": 0,
                "max_execution_time_ms": 0
            }
        
        return {
            "execution_count": len(metrics),
            "avg_execution_time_ms": round(sum(metrics) / len(metrics), 2),
            "min_execution_time_ms": round(min(metrics), 2),
            "max_execution_time_ms": round(max(metrics), 2),
            "recent_executions": metrics[-10:]  # Last 10 executions
        }
    
    def get_all_performance_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get performance metrics for all tools.
        
        Returns:
            Dictionary mapping tool names to their performance metrics
        """
        return {
            tool_name: self.get_tool_performance_metrics(tool_name)
            for tool_name in self.performance_metrics.keys()
        }
    
    async def cache_tool_result(
        self,
        cache_key: str,
        result: Any,
        ttl_seconds: int = 300
    ) -> None:
        """
        Cache a tool execution result for performance optimization.
        
        Args:
            cache_key: Unique key for the cached result
            result: Result to cache
            ttl_seconds: Time to live in seconds
        """
        try:
            # Simple in-memory cache with TTL
            # In production, this could use Redis
            cache_entry = {
                "result": result,
                "cached_at": datetime.now(timezone.utc),
                "ttl_seconds": ttl_seconds
            }
            
            self.execution_cache[cache_key] = cache_entry
            
            # Clean up expired entries periodically
            await self._cleanup_expired_cache_entries()
            
        except Exception as e:
            logger.warning("Failed to cache tool result: %s", e)
    
    async def get_cached_result(self, cache_key: str) -> Optional[Any]:
        """
        Get a cached tool execution result if available and not expired.
        
        Args:
            cache_key: Cache key to look up
            
        Returns:
            Cached result if available and valid, None otherwise
        """
        try:
            if cache_key not in self.execution_cache:
                return None
            
            cache_entry = self.execution_cache[cache_key]
            cached_at = cache_entry["cached_at"]
            ttl_seconds = cache_entry["ttl_seconds"]
            
            # Check if cache entry is still valid
            now = datetime.now(timezone.utc)
            if (now - cached_at).total_seconds() > ttl_seconds:
                # Cache expired, remove it
                del self.execution_cache[cache_key]
                return None
            
            return cache_entry["result"]
            
        except Exception as e:
            logger.warning("Failed to get cached result: %s", e)
            return None
    
    async def _cleanup_expired_cache_entries(self) -> None:
        """Clean up expired cache entries to prevent memory leaks."""
        try:
            now = datetime.now(timezone.utc)
            expired_keys = []
            
            for cache_key, cache_entry in self.execution_cache.items():
                cached_at = cache_entry["cached_at"]
                ttl_seconds = cache_entry["ttl_seconds"]
                
                if (now - cached_at).total_seconds() > ttl_seconds:
                    expired_keys.append(cache_key)
            
            for key in expired_keys:
                del self.execution_cache[key]
            
            if expired_keys:
                logger.debug("Cleaned up %d expired cache entries", len(expired_keys))
                
        except Exception as e:
            logger.warning("Failed to cleanup expired cache entries: %s", e)


# Global tool coordinator instance
_global_tool_coordinator: Optional[ToolCoordinator] = None


def get_global_tool_coordinator() -> Optional[ToolCoordinator]:
    """
    Get the global tool coordinator instance.
    
    Returns:
        The global tool coordinator instance or None if not initialized
    """
    global _global_tool_coordinator
    return _global_tool_coordinator


def set_global_tool_coordinator(coordinator: ToolCoordinator):
    """
    Set the global tool coordinator instance.
    
    Args:
        coordinator: The tool coordinator instance to set as global
    """
    global _global_tool_coordinator
    _global_tool_coordinator = coordinator


def initialize_global_tool_coordinator() -> ToolCoordinator:
    """
    Initialize and return the global tool coordinator instance.
    
    Returns:
        The initialized global tool coordinator instance
    """
    global _global_tool_coordinator
    if _global_tool_coordinator is None:
        _global_tool_coordinator = ToolCoordinator()
    return _global_tool_coordinator


# Global instance will be created lazily when needed
tool_coordinator = None