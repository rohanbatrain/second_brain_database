"""
FastMCP 2.x Authentication Middleware

Production-ready authentication middleware that integrates with the existing
Second Brain Database authentication system and provides proper user context
for MCP tool execution.
"""

import asyncio
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException, Request
from fastmcp.server.auth.auth import AccessToken, AuthProvider

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

logger = get_logger(prefix="[MCP_Auth]")


class FastMCPJWTAuthProvider(AuthProvider):
    """
    FastMCP 2.x compliant JWT authentication provider.

    This provider follows the FastMCP 2.x authentication interface and
    integrates with the existing Second Brain Database JWT system.
    """

    def __init__(self):
        super().__init__(base_url=None, required_scopes=[])
        self.name = "FastMCPJWTAuth"
        logger.info("Initialized FastMCP 2.x JWT authentication provider")

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """
        FastMCP 2.x token verification interface.

        Args:
            token: Bearer token from Authorization header

        Returns:
            AccessToken object if valid, None if invalid

        Raises:
            Exception: If authentication fails
        """
        try:
            # Use existing JWT validation
            authenticated_user = await self._validate_jwt_token(token)

            # Return AccessToken in FastMCP format
            return AccessToken(
                token=token,
                sub=str(authenticated_user["_id"]),
                scopes=[],
                metadata={
                    "username": authenticated_user.get("username"),
                    "email": authenticated_user.get("email"),
                    "role": authenticated_user.get("role", "user"),
                    "permissions": authenticated_user.get("permissions", []),
                    "family_memberships": authenticated_user.get("family_memberships", []),
                    "workspaces": authenticated_user.get("workspaces", []),
                }
            )

        except Exception as e:
            logger.error("FastMCP JWT authentication failed: %s", e)
            return None

    async def _validate_jwt_token(self, token: str) -> Dict[str, Any]:
        """Validate JWT token using existing system."""
        from ...routes.auth.services.auth.login import get_current_user

        return await get_current_user(token)


class SecondBrainAuthProvider:
    """
    Legacy authentication provider (kept for backward compatibility).

    This provider integrates with the existing Second Brain Database
    authentication system and provides proper user context for MCP operations.
    """

    def __init__(self):
        self.name = "SecondBrainAuth"
        logger.info("Initialized Second Brain MCP authentication provider")

    async def authenticate(self, request: Request) -> Dict[str, Any]:
        """
        Authenticate MCP request using existing JWT authentication system.

        This method validates JWT tokens using the same authentication system
        as the main FastAPI application, ensuring consistent user context.

        Args:
            request: FastAPI Request object

        Returns:
            Dictionary with authentication result containing real user data

        Raises:
            HTTPException: If authentication fails
        """
        try:
            # Extract authorization header
            authorization = request.headers.get("Authorization")
            if not authorization or not authorization.startswith("Bearer "):
                # For development/testing, allow requests without auth if disabled
                if not settings.MCP_SECURITY_ENABLED or not settings.MCP_REQUIRE_AUTH:
                    logger.warning("MCP request without authentication - development mode")
                    user_context = await self._create_development_user_context(request)
                    await self._set_mcp_context(user_context, request)

                    return {
                        "success": True,
                        "user_id": "dev-user",
                        "metadata": {"username": "development-user", "role": "admin", "mode": "development"},
                    }

                raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

            token = authorization.split(" ")[1]

            # Use existing JWT authentication system to get real user
            authenticated_user = await self._authenticate_with_jwt(token)

            # Create MCP user context from real authenticated user
            client_info = await extract_client_info_from_request(request)
            user_context = await create_mcp_user_context_from_fastapi_user(
                fastapi_user=authenticated_user,
                ip_address=client_info["ip_address"],
                user_agent=client_info["user_agent"],
                token_type="jwt",
                token_id=None,
            )

            await self._set_mcp_context(user_context, request)

            logger.info(
                "MCP authenticated user: %s (%s) with %d permissions",
                user_context.username,
                user_context.user_id,
                len(user_context.permissions),
            )

            return {
                "success": True,
                "user_id": user_context.user_id,
                "metadata": {
                    "username": user_context.username,
                    "email": user_context.email,
                    "role": user_context.role,
                    "mode": "jwt",
                    "permissions": user_context.permissions,
                },
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error("MCP authentication error: %s", e)
            return {"success": False, "error": str(e)}

    async def _authenticate_with_jwt(self, token: str) -> Dict[str, Any]:
        """
        Authenticate using existing JWT system.

        This uses the same get_current_user function that the main FastAPI
        application uses, ensuring consistent authentication behavior.

        Args:
            token: JWT token from Authorization header

        Returns:
            User dictionary from existing authentication system with all user data

        Raises:
            HTTPException: If JWT validation fails
        """
        try:
            # Import here to avoid circular imports
            from ...routes.auth.services.auth.login import get_current_user

            # Use the same JWT validation as the main application
            authenticated_user = await get_current_user(token)

            if not authenticated_user:
                raise HTTPException(status_code=401, detail="Invalid authentication token")

            logger.debug(
                "JWT authentication successful for user: %s (%s)",
                authenticated_user.get("username"),
                authenticated_user.get("_id"),
            )

            return authenticated_user

        except HTTPException:
            raise
        except Exception as e:
            logger.error("JWT authentication failed: %s", e)
            raise HTTPException(status_code=401, detail="JWT authentication failed")

    async def _create_development_user_context(self, request: Request) -> MCPUserContext:
        """
        Create development user context.

        Args:
            request: FastAPI Request object

        Returns:
            MCPUserContext for development
        """
        from datetime import datetime, timezone

        client_info = await extract_client_info_from_request(request)

        return MCPUserContext(
            user_id="dev-user",
            username="development-user",
            email="dev@localhost",
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

    async def _set_mcp_context(self, user_context: MCPUserContext, request: Request) -> None:
        """
        Set MCP context for the request.

        Args:
            user_context: User context to set
            request: FastAPI Request object
        """
        # Set user context
        set_mcp_user_context(user_context)

        # Create and set request context
        request_context = create_mcp_request_context(
            operation_type="tool", parameters={}  # Default, will be updated by tool decorators
        )
        set_mcp_request_context(request_context)

        logger.debug("Set MCP context for user %s (%s mode)", user_context.user_id, user_context.token_type)


class MCPAuthenticationMiddleware:
    """
    Authentication middleware for FastMCP 2.x HTTP transport.

    This middleware handles JWT authentication for MCP requests and sets
    the user context for tool execution.
    """

    def __init__(self, app: Callable):
        self.app = app
        self.auth_provider = SecondBrainAuthProvider()

    async def __call__(self, scope: dict, receive: Callable, send: Callable):
        """
        ASGI middleware implementation for authentication.

        Args:
            scope: ASGI scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        # Only authenticate HTTP requests to MCP endpoints
        if scope["type"] == "http" and scope["path"].startswith("/mcp"):
            try:
                # Create a FastAPI Request object for authentication
                from fastapi import Request

                request = Request(scope, receive)

                # Authenticate the request
                auth_result = await self.auth_provider.authenticate(request)

                if not auth_result.get("success"):
                    # Authentication failed - return 401
                    response = {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [[b"content-type", b"application/json"]],
                    }
                    await send(response)

                    body = {
                        "type": "http.response.body",
                        "body": b'{"error": "Authentication required"}',
                    }
                    await send(body)
                    return

                # Authentication successful - continue with request
                await self.app(scope, receive, send)

            except Exception as e:
                logger.error("Authentication middleware error: %s", e)
                # Return 500 on authentication error
                response = {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [[b"content-type", b"application/json"]],
                }
                await send(response)

                body = {
                    "type": "http.response.body",
                    "body": b'{"error": "Authentication error"}',
                }
                await send(body)
                return
            finally:
                # Always clean up MCP context
                try:
                    clear_mcp_context()
                except Exception as e:
                    logger.warning("Failed to clear MCP context: %s", e)
        else:
            # Non-MCP requests pass through without authentication
            await self.app(scope, receive, send)


class MCPContextMiddleware:
    """
    Middleware to ensure proper MCP context cleanup.

    This middleware ensures that MCP context is properly cleaned up
    after each request to prevent context leakage.
    """

    def __init__(self, app: Callable):
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable):
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


def create_mcp_auth_provider() -> Optional[SecondBrainAuthProvider]:
    """
    Create MCP authentication provider based on configuration.

    Returns:
        SecondBrainAuthProvider if authentication is enabled, None otherwise
    """
    # For STDIO transport, no authentication needed (process-level security)
    if settings.MCP_TRANSPORT == "stdio":
        logger.info("MCP STDIO transport - no authentication provider needed")
        return None

    # For HTTP transport, always create provider (it handles dev/prod modes internally)
    logger.info("Creating Second Brain MCP authentication provider")
    return SecondBrainAuthProvider()


def create_mcp_context_middleware() -> MCPContextMiddleware:
    """
    Create MCP context cleanup middleware.

    Returns:
        MCPContextMiddleware instance
    """
    return MCPContextMiddleware
