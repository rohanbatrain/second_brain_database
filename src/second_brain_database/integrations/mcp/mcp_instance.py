"""
Shared FastMCP Instance

Provides a shared FastMCP instance that can be used across all tools,
resources, and prompts for consistent registration and management.
"""

from typing import Optional
from ...managers.logging_manager import get_logger
from ...config import settings

logger = get_logger(prefix="[MCP_Instance]")

# Global FastMCP instance - will be initialized when FastMCP is available
mcp: Optional[object] = None

def get_mcp_instance():
    """
    Get the shared FastMCP instance.
    
    Returns:
        The FastMCP instance if available, None otherwise
    """
    global mcp
    
    if mcp is None:
        try:
            from fastmcp import FastMCP
            mcp = FastMCP(
                name=settings.MCP_SERVER_NAME,
                version=settings.MCP_SERVER_VERSION
            )
            logger.info("Created shared FastMCP instance: %s v%s", 
                       settings.MCP_SERVER_NAME, settings.MCP_SERVER_VERSION)
        except ImportError:
            logger.warning("FastMCP library not available - resources and prompts will not be registered")
            return None
        except Exception as e:
            logger.error("Failed to create FastMCP instance: %s", e)
            return None
    
    return mcp

def reset_mcp_instance():
    """Reset the global MCP instance (for testing purposes)."""
    global mcp
    mcp = None

# Initialize the instance on import
_instance = get_mcp_instance()