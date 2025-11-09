"""
FastMCP 2.x Prompt Registration

DEPRECATED: This module contains old prompt registrations that have been replaced
by the production-ready prompts in prompts/guidance_prompts.py.

The prompts below are commented out to prevent duplicates. The new prompts include:
- User context personalization
- Database-driven status checks
- Production-ready audit trails
- Comprehensive guidance

DO NOT RE-ENABLE THESE PROMPTS. Use prompts/guidance_prompts.py instead.
"""

from datetime import datetime
from typing import Any, Dict, List

from ...managers.logging_manager import get_logger
from .modern_server import mcp

logger = get_logger(prefix="[MCP_Prompts_DEPRECATED]")


# DEPRECATED: Replaced by prompts/guidance_prompts.py
# Kept here for reference only - DO NOT UNCOMMENT

# @mcp.prompt
# def server_help() -> str:
#     """Provide help information about the MCP server."""
#     return f"""# Second Brain Database MCP Server Help
# ...
# """


# DEPRECATED: Replaced by prompts/guidance_prompts.py api_usage_guide
# @mcp.prompt(
#     name="api_usage_guide",
#     description="Provides comprehensive guidance on using the MCP API",
#     tags={"documentation", "api"}
# )
# def api_usage_guide_prompt() -> str:
#     """Provide guidance on using the MCP API."""
#     return """# MCP API Usage Guide
# ...
# """


# DEPRECATED: Replaced by prompts/guidance_prompts.py troubleshooting_guide
# @mcp.prompt("troubleshooting_guide")
# async def troubleshooting_guide_prompt() -> str:
#     """Provide troubleshooting guidance for common issues."""
#     return f"""
# # MCP Server Troubleshooting Guide
# ...
# """


# DEPRECATED: No replacement needed - development guide not used in production
# @mcp.prompt("development_guide")
# async def development_guide_prompt() -> str:
#     """Provide guidance for developers working with the MCP server."""
#     return """
# # MCP Server Development Guide
# ...
# """


# DEPRECATED: No replacement needed - security guide integrated into security_setup_guide
# @mcp.prompt("security_guide")
# async def security_guide_prompt() -> str:
#     """Provide security guidance for the MCP server."""
#     return f"""
# # MCP Server Security Guide
# ...
# """


def register_example_prompts():
    """
    DEPRECATED: Prompts are no longer registered from this module.

    All production prompts are now registered from prompts/guidance_prompts.py
    which includes user context, database integration, and comprehensive guidance.

    This function is kept for backwards compatibility but does nothing.
    """
    logger.warning("prompts_registration.py is DEPRECATED - use prompts/guidance_prompts.py instead")
    logger.info("Production prompts are registered from prompts/guidance_prompts.py")


# Auto-register prompts when module is imported (DEPRECATED - does nothing now)
register_example_prompts()
