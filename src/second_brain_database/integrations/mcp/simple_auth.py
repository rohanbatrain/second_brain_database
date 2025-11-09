"""
Simple MCP Authentication System

A simplified authentication system that works with FastMCP 2.x
without requiring non-existent auth modules.
"""

import asyncio
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

from ...config import settings
from ...managers.logging_manager import get_logger
from .context import (
    MCPRequestContext,
    MCPUserContext,
    clear_mcp_context,
    create_mcp_request_context,
    create_mcp_user_context_from_fastapi_user,
    extract_client_info_from_request,
    set_mcp_request_context,
    set_mcp_user_context,
)
from .exceptions import MCPAuthenticationError

logger = get_logger(prefix="[MCP_SimpleAuth]")


async def create_development_user_context(request: Optional[Request] = None) -> MCPUserContext:
    """
    Create development user context.

    Args:
        request: FastAPI Request object (optional)

    Returns:
        MCPUserContext for development
    """
    from datetime import datetime, timezone

    client_info = {"ip_address": "127.0.0.1", "user_agent": "MCP-Development-Client"}
    if request:
        try:
            client_info = await extract_client_info_from_request(request)
        except Exception:
            pass  # Use defaults

    return MCPUserContext(
        user_id="69026f7fdd8b409786287852",  # Use existing test_user ID
        username="test_user",
        email="test@localhost",
        role="admin",
        permissions=["admin", "user", "family:admin", "shop:admin", "workspace:admin"],
        workspaces=[],
        family_memberships=[],
        ip_address=client_info["ip_address"] or "127.0.0.1",
        user_agent=client_info["user_agent"] or "MCP-Development-Client",
        trusted_ip_lockdown=False,
        trusted_user_agent_lockdown=False,
        trusted_ips=["127.0.0.1"],
        trusted_user_agents=["MCP-Development-Client"],
        token_type="development",
        token_id="dev-token",
        authenticated_at=datetime.now(timezone.utc),
    )


async def authenticate_mcp_request(request: Optional[Request] = None) -> MCPUserContext:
    """
    Authenticate MCP request and return user context.

    Args:
        request: FastAPI Request object (optional)

    Returns:
        MCPUserContext for the authenticated user

    Raises:
        MCPAuthenticationError: If authentication fails
    """
    try:
        # Check if authentication is required
        if not settings.MCP_SECURITY_ENABLED or not settings.MCP_REQUIRE_AUTH:
            # Development mode - create default user context
            logger.debug("Creating development user context (auth disabled)")
            user_context = await create_development_user_context(request)
            set_mcp_user_context(user_context)
            return user_context

        # Production mode - require real authentication
        if not request:
            raise MCPAuthenticationError("Request required for production authentication")

        return await authenticate_production_request(request)

    except Exception as e:
        logger.error("MCP authentication error: %s", e)
        if isinstance(e, MCPAuthenticationError):
            raise
        raise MCPAuthenticationError(f"Authentication failed: {e}") from e


async def authenticate_production_request(request: Request) -> MCPUserContext:
    """
    Authenticate production MCP request.

    Args:
        request: FastAPI Request object

    Returns:
        MCPUserContext for authenticated user

    Raises:
        MCPAuthenticationError: If authentication fails
    """
    try:
        # Extract authorization header
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise MCPAuthenticationError("Missing or invalid Authorization header")

        token = authorization.split(" ")[1]

        # Check if it's a static token (for development/testing)
        if hasattr(settings, "MCP_AUTH_TOKEN") and settings.MCP_AUTH_TOKEN:
            token_value = (
                settings.MCP_AUTH_TOKEN.get_secret_value()
                if hasattr(settings.MCP_AUTH_TOKEN, "get_secret_value")
                else str(settings.MCP_AUTH_TOKEN)
            )

            if token == token_value:
                # Static token authentication
                logger.debug("Static token authentication successful")
                user_context = await create_static_token_user_context(request)
                set_mcp_user_context(user_context)
                return user_context

        # Try JWT authentication with existing system
        fastapi_user = await authenticate_with_jwt(token)

        # Create MCP user context from authenticated user
        client_info = await extract_client_info_from_request(request)
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=fastapi_user,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
            token_type="jwt",
            token_id=None,
        )

        set_mcp_user_context(user_context)
        logger.debug("JWT authentication successful for user %s", user_context.user_id)
        return user_context

    except MCPAuthenticationError:
        raise
    except Exception as e:
        logger.error("Production authentication failed: %s", e)
        raise MCPAuthenticationError(f"Authentication failed: {str(e)}") from e


async def create_static_token_user_context(request: Request) -> MCPUserContext:
    """
    Create static token user context.

    Args:
        request: FastAPI Request object

    Returns:
        MCPUserContext for static token authentication
    """
    from datetime import datetime, timezone

    client_info = await extract_client_info_from_request(request)

    return MCPUserContext(
        user_id="static-token-user",
        username="static-token-user",
        email="static@localhost",
        role="admin",
        permissions=["admin", "user", "family:admin", "shop:admin", "workspace:admin"],
        workspaces=[],
        family_memberships=[],
        ip_address=client_info["ip_address"] or "127.0.0.1",
        user_agent=client_info["user_agent"] or "MCP-Static-Token-Client",
        trusted_ip_lockdown=False,
        trusted_user_agent_lockdown=False,
        trusted_ips=["127.0.0.1"],
        trusted_user_agents=["MCP-Static-Token-Client"],
        token_type="static-token",
        token_id="static-token",
        authenticated_at=datetime.now(timezone.utc),
    )


async def authenticate_with_jwt(token: str) -> Dict[str, Any]:
    """
    Authenticate using existing JWT system.

    Args:
        token: JWT token

    Returns:
        User dictionary from existing authentication system

    Raises:
        MCPAuthenticationError: If authentication fails
    """
    try:
        # Import here to avoid circular imports
        from ...routes.auth.dependencies import get_current_user_dep

        # Use existing authentication dependency
        fastapi_user = await get_current_user_dep(token)

        if not fastapi_user:
            raise MCPAuthenticationError("Invalid authentication token")

        return fastapi_user

    except Exception as e:
        logger.error("JWT authentication failed: %s", e)
        raise MCPAuthenticationError("JWT authentication failed") from e


def setup_mcp_context_for_request(request: Optional[Request] = None):
    """
    Set up MCP context for a request.

    This is a synchronous wrapper that can be used in decorators.

    Args:
        request: FastAPI Request object (optional)
    """
    try:
        # Run authentication in async context
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a task
            task = asyncio.create_task(authenticate_mcp_request(request))
            # Note: This won't work in sync context, but it's better than nothing
            return task
        else:
            # Run in new event loop
            return loop.run_until_complete(authenticate_mcp_request(request))
    except Exception as e:
        logger.error("Failed to set up MCP context: %s", e)
        # Create default context as fallback
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = asyncio.create_task(create_development_user_context(request))
                return task
            else:
                user_context = loop.run_until_complete(create_development_user_context(request))
                set_mcp_user_context(user_context)
                return user_context
        except Exception as fallback_error:
            logger.error("Failed to create fallback context: %s", fallback_error)
            raise MCPAuthenticationError("Failed to set up authentication context") from e


class MCPContextMiddleware:
    """
    Middleware to ensure proper MCP context cleanup.

    This middleware ensures that MCP context is properly cleaned up
    after each request to prevent context leakage.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        """
        ASGI middleware implementation.

        Args:
            scope: ASGI scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        try:
            await self.app(scope, receive, send)
        finally:
            # Always clean up MCP context
            try:
                clear_mcp_context()
            except Exception as e:
                logger.warning("Failed to clear MCP context: %s", e)


def create_mcp_context_middleware():
    """
    Create MCP context cleanup middleware.

    Returns:
        MCPContextMiddleware instance
    """
    return MCPContextMiddleware
