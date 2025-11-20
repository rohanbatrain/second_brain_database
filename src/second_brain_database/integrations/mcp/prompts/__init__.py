"""
MCP Prompts

This package contains all MCP prompt implementations that provide
contextual guidance for various operations and user assistance.
Prompts are automatically discovered and registered with the FastMCP server.
"""

# Prompt modules - import to register with FastMCP
from . import guidance_prompts

__all__ = ["guidance_prompts"]
