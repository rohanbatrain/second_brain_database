"""
MCP Context Management

Context management for MCP operations including user authentication,
request tracking, and security context integration with existing FastAPI patterns.
"""

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from ...config import settings
from ...managers.logging_manager import get_logger
from .exceptions import MCPAuthenticationError, MCPAuthorizationError

logger = get_logger(prefix="[MCP Context]")

# Context variables for MCP request tracking
_mcp_user_context: ContextVar[Optional["MCPUserContext"]] = ContextVar("mcp_user_context", default=None)
_mcp_request_context: ContextVar[Optional["MCPRequestContext"]] = ContextVar("mcp_request_context", default=None)


@dataclass
class MCPUserContext:
    """
    User context for MCP operations.

    Contains user identity, permissions, and security information
    extracted from authentication tokens and user profiles.
    Integrates with existing FastAPI authentication patterns.
    """

    user_id: str
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    workspaces: List[Dict[str, Any]] = field(default_factory=list)

    # Security context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    trusted_ip_lockdown: bool = False
    trusted_user_agent_lockdown: bool = False
    trusted_ips: List[str] = field(default_factory=list)
    trusted_user_agents: List[str] = field(default_factory=list)

    # Authentication metadata
    token_type: Optional[str] = None  # 'jwt' or 'permanent'
    token_id: Optional[str] = None
    authenticated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Family context (for family-related operations)
    family_memberships: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging and serialization."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "permissions": self.permissions,
            "workspaces": [
                {"id": ws.get("_id"), "name": ws.get("name"), "role": ws.get("role")} for ws in self.workspaces
            ],
            "family_memberships": [
                {"id": fm.get("family_id"), "role": fm.get("role")} for fm in self.family_memberships
            ],
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "trusted_ip_lockdown": self.trusted_ip_lockdown,
            "trusted_user_agent_lockdown": self.trusted_user_agent_lockdown,
            "token_type": self.token_type,
            "token_id": self.token_id,
            "authenticated_at": self.authenticated_at.isoformat(),
        }

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        if self.role == "admin":
            return True
        if not self.permissions:
            return False
        return permission in self.permissions

    def has_any_permission(self, permissions: List[str]) -> bool:
        """Check if user has any of the specified permissions."""
        if self.role == "admin":
            return True
        if not self.permissions:
            return False
        return any(perm in self.permissions for perm in permissions)

    def has_all_permissions(self, permissions: List[str]) -> bool:
        """Check if user has all of the specified permissions."""
        if self.role == "admin":
            return True
        if not self.permissions:
            return False
        return all(perm in self.permissions for perm in permissions)

    def is_workspace_member(self, workspace_id: str) -> bool:
        """Check if user is a member of the specified workspace."""
        return any(str(ws.get("_id")) == workspace_id for ws in self.workspaces)

    def get_workspace_role(self, workspace_id: str) -> Optional[str]:
        """Get user's role in the specified workspace."""
        for ws in self.workspaces:
            if str(ws.get("_id")) == workspace_id:
                return ws.get("role")
        return None

    def is_family_member(self, family_id: str) -> bool:
        """Check if user is a member of the specified family."""
        return any(str(fm.get("family_id")) == family_id for fm in self.family_memberships)

    def get_family_role(self, family_id: str) -> Optional[str]:
        """Get user's role in the specified family."""
        for fm in self.family_memberships:
            if str(fm.get("family_id")) == family_id:
                return fm.get("role")
        return None

    def is_family_admin(self, family_id: str) -> bool:
        """Check if user is an admin of the specified family."""
        role = self.get_family_role(family_id)
        return role in ["admin", "owner"]

    def can_access_family(self, family_id: str, required_role: Optional[str] = None) -> bool:
        """Check if user can access a family with optional role requirement."""
        if not self.is_family_member(family_id):
            return False

        if required_role is None:
            return True

        user_role = self.get_family_role(family_id)
        if user_role == "owner":
            return True
        elif user_role == "admin" and required_role in ["admin", "member"]:
            return True
        elif user_role == "member" and required_role == "member":
            return True

        return False


@dataclass
class MCPRequestContext:
    """
    Request context for MCP operations.

    Contains request-specific information for tracking, auditing,
    and security monitoring of MCP tool executions.
    """

    request_id: str
    tool_name: Optional[str] = None
    resource_uri: Optional[str] = None
    prompt_name: Optional[str] = None
    operation_type: str = "unknown"  # 'tool', 'resource', 'prompt'

    # Request metadata
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None

    # Request parameters (sanitized for logging)
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Rate limiting context
    rate_limit_key: Optional[str] = None
    rate_limit_remaining: Optional[int] = None

    # Error context
    error_occurred: bool = False
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    # Security context
    security_checks_passed: bool = False
    permission_checks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging and serialization."""
        return {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "resource_uri": self.resource_uri,
            "prompt_name": self.prompt_name,
            "operation_type": self.operation_type,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "parameters": self.parameters,
            "rate_limit_key": self.rate_limit_key,
            "rate_limit_remaining": self.rate_limit_remaining,
            "error_occurred": self.error_occurred,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "security_checks_passed": self.security_checks_passed,
            "permission_checks": self.permission_checks,
        }

    def mark_completed(self, error: Optional[Exception] = None) -> None:
        """Mark the request as completed and calculate duration."""
        self.completed_at = datetime.now(timezone.utc)
        self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000

        if error:
            self.error_occurred = True
            self.error_type = type(error).__name__
            self.error_message = str(error)

    def add_permission_check(self, permission: str) -> None:
        """Add a permission check to the audit trail."""
        if permission not in self.permission_checks:
            self.permission_checks.append(permission)


async def get_current_mcp_user() -> Optional[MCPUserContext]:
    """
    Get the current MCP user context.

    Returns the user context for the current MCP operation,
    or None if no user context is available.

    Returns:
        MCPUserContext or None
    """
    try:
        return _mcp_user_context.get()
    except LookupError:
        return None


def get_mcp_user_context() -> MCPUserContext:
    """
    Get the current MCP user context (required).

    Returns the user context for the current MCP operation.
    Raises an exception if no user context is available.

    Returns:
        MCPUserContext

    Raises:
        MCPAuthenticationError: If no user context is available
    """
    context = _mcp_user_context.get(None)
    if context is None:
        raise MCPAuthenticationError("No MCP user context available - authentication required")
    return context


async def get_current_mcp_request() -> Optional[MCPRequestContext]:
    """
    Get the current MCP request context.

    Returns the request context for the current MCP operation,
    or None if no request context is available.

    Returns:
        MCPRequestContext or None
    """
    try:
        return _mcp_request_context.get()
    except LookupError:
        return None


def get_mcp_request_context() -> MCPRequestContext:
    """
    Get the current MCP request context (required).

    Returns the request context for the current MCP operation.
    Raises an exception if no request context is available.

    Returns:
        MCPRequestContext

    Raises:
        RuntimeError: If no request context is available
    """
    context = _mcp_request_context.get(None)
    if context is None:
        raise RuntimeError("No MCP request context available")
    return context


def set_mcp_user_context(context: MCPUserContext) -> None:
    """
    Set the MCP user context for the current operation.

    Args:
        context: User context to set
    """
    _mcp_user_context.set(context)
    logger.debug("Set MCP user context for user %s", context.user_id)


def set_mcp_request_context(context: MCPRequestContext) -> None:
    """
    Set the MCP request context for the current operation.

    Args:
        context: Request context to set
    """
    _mcp_request_context.set(context)
    logger.debug("Set MCP request context for request %s", context.request_id)


def clear_mcp_context() -> None:
    """
    Clear all MCP context variables.

    Should be called at the end of MCP operations to prevent
    context leakage between requests.
    """
    _mcp_user_context.set(None)
    _mcp_request_context.set(None)
    logger.debug("Cleared MCP context")


async def create_mcp_user_context_from_fastapi_user(
    fastapi_user: Dict[str, Any],
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    token_type: Optional[str] = None,
    token_id: Optional[str] = None,
) -> MCPUserContext:
    """
    Create MCP user context from FastAPI user object.

    Converts the user object returned by get_current_user_dep
    into an MCPUserContext with proper security information.

    Args:
        fastapi_user: User object from FastAPI authentication
        ip_address: Client IP address
        user_agent: Client user agent
        token_type: Type of authentication token used
        token_id: ID of the authentication token

    Returns:
        MCPUserContext instance

    Raises:
        MCPAuthenticationError: If user context creation fails
    """
    try:
        # Extract basic user information
        user_id = str(fastapi_user["_id"])
        username = fastapi_user.get("username")
        email = fastapi_user.get("email")
        role = fastapi_user.get("role", "user")

        # Extract permissions (if available)
        permissions = fastapi_user.get("permissions", [])
        if isinstance(permissions, str):
            permissions = [permissions]

        # Extract workspace information
        workspaces = fastapi_user.get("workspaces", [])

        # Extract family memberships (if available)
        family_memberships = fastapi_user.get("family_memberships", [])

        # Extract security settings
        trusted_ip_lockdown = fastapi_user.get("trusted_ip_lockdown", False)
        trusted_user_agent_lockdown = fastapi_user.get("trusted_user_agent_lockdown", False)
        trusted_ips = fastapi_user.get("trusted_ips", [])
        trusted_user_agents = fastapi_user.get("trusted_user_agents", [])

        # Create MCP user context
        context = MCPUserContext(
            user_id=user_id,
            username=username,
            email=email,
            role=role,
            permissions=permissions,
            workspaces=workspaces,
            family_memberships=family_memberships,
            ip_address=ip_address,
            user_agent=user_agent,
            trusted_ip_lockdown=trusted_ip_lockdown,
            trusted_user_agent_lockdown=trusted_user_agent_lockdown,
            trusted_ips=trusted_ips,
            trusted_user_agents=trusted_user_agents,
            token_type=token_type,
            token_id=token_id,
        )

        logger.debug("Created MCP user context for user %s (%s)", user_id, username)
        return context

    except Exception as e:
        logger.error("Failed to create MCP user context: %s", e)
        raise MCPAuthenticationError(f"Failed to create MCP user context: {e}") from e


def create_mcp_request_context(
    request_id: Optional[str] = None,
    operation_type: str = "unknown",
    tool_name: Optional[str] = None,
    resource_uri: Optional[str] = None,
    prompt_name: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
) -> MCPRequestContext:
    """
    Create MCP request context for tracking operations.

    Args:
        request_id: Unique request identifier (generated if None)
        operation_type: Type of operation ('tool', 'resource', 'prompt')
        tool_name: Name of MCP tool being executed
        resource_uri: URI of MCP resource being accessed
        prompt_name: Name of MCP prompt being generated
        parameters: Request parameters (will be sanitized)

    Returns:
        MCPRequestContext instance
    """
    if request_id is None:
        request_id = str(uuid.uuid4())

    # Sanitize parameters for logging
    sanitized_params = {}
    if parameters:
        for key, value in parameters.items():
            # Sanitize sensitive parameter names
            if any(
                sensitive in key.lower() for sensitive in ["password", "token", "secret", "key", "auth", "credential"]
            ):
                sanitized_params[key] = "<REDACTED>"
            else:
                # Convert complex objects to strings for logging
                if isinstance(value, (dict, list)):
                    str_value = str(value)
                    sanitized_params[key] = str_value[:100] + "..." if len(str_value) > 100 else str_value
                else:
                    sanitized_params[key] = value

    context = MCPRequestContext(
        request_id=request_id,
        operation_type=operation_type,
        tool_name=tool_name,
        resource_uri=resource_uri,
        prompt_name=prompt_name,
        parameters=sanitized_params,
    )

    logger.debug(
        "Created MCP request context for %s operation: %s",
        operation_type,
        tool_name or resource_uri or prompt_name or "unknown",
    )

    return context


async def validate_mcp_user_permissions(
    required_permissions: List[str], user_context: Optional[MCPUserContext] = None
) -> bool:
    """
    Validate that the current user has required permissions.

    Args:
        required_permissions: List of required permissions
        user_context: User context (uses current context if None)

    Returns:
        True if user has all required permissions, False otherwise

    Raises:
        MCPAuthenticationError: If no user context is available
    """
    if not required_permissions:
        return True

    if user_context is None:
        user_context = await get_current_mcp_user()

    if user_context is None:
        raise MCPAuthenticationError("No user context available for permission validation")

    # Add permission checks to request context for auditing
    request_context = await get_current_mcp_request()
    if request_context:
        for perm in required_permissions:
            request_context.add_permission_check(perm)

    has_permissions = user_context.has_all_permissions(required_permissions)

    if not has_permissions:
        logger.warning(
            "User %s lacks required permissions. Required: %s, Has: %s",
            user_context.user_id,
            required_permissions,
            user_context.permissions,
        )

    return has_permissions


async def require_mcp_permissions(
    required_permissions: List[str], user_context: Optional[MCPUserContext] = None
) -> MCPUserContext:
    """
    Require that the current user has specified permissions.

    Args:
        required_permissions: List of required permissions
        user_context: User context (uses current context if None)

    Returns:
        MCPUserContext if permissions are satisfied

    Raises:
        MCPAuthenticationError: If no user context is available
        MCPAuthorizationError: If user lacks required permissions
    """
    if user_context is None:
        user_context = await get_current_mcp_user()

    if user_context is None:
        raise MCPAuthenticationError("Authentication required for this operation")

    if not await validate_mcp_user_permissions(required_permissions, user_context):
        raise MCPAuthorizationError(
            f"Insufficient permissions for operation",
            required_permissions=required_permissions,
            user_permissions=user_context.permissions,
        )

    return user_context


async def validate_family_access(
    family_id: str, required_role: Optional[str] = None, user_context: Optional[MCPUserContext] = None
) -> bool:
    """
    Validate that the current user can access a specific family.

    Args:
        family_id: Family ID to check access for
        required_role: Required role in the family (None for any member)
        user_context: User context (uses current context if None)

    Returns:
        True if user can access the family, False otherwise
    """
    if user_context is None:
        user_context = await get_current_mcp_user()

    if user_context is None:
        return False

    return user_context.can_access_family(family_id, required_role)


async def require_family_access(
    family_id: str, required_role: Optional[str] = None, user_context: Optional[MCPUserContext] = None
) -> MCPUserContext:
    """
    Require that the current user can access a specific family.

    Args:
        family_id: Family ID to check access for
        required_role: Required role in the family (None for any member)
        user_context: User context (uses current context if None)

    Returns:
        MCPUserContext if access is granted

    Raises:
        MCPAuthenticationError: If no user context is available
        MCPAuthorizationError: If user cannot access the family
    """
    if user_context is None:
        user_context = await get_current_mcp_user()

    if user_context is None:
        raise MCPAuthenticationError("Authentication required for family access")

    if not await validate_family_access(family_id, required_role, user_context):
        user_role = user_context.get_family_role(family_id)
        raise MCPAuthorizationError(
            f"Insufficient access to family {family_id}",
            context={
                "family_id": family_id,
                "required_role": required_role,
                "user_role": user_role,
                "is_member": user_context.is_family_member(family_id),
            },
        )

    return user_context


async def log_mcp_operation(
    operation_name: str,
    success: bool = True,
    error: Optional[Exception] = None,
    additional_context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log MCP operation with full context information.

    Args:
        operation_name: Name of the operation being logged
        success: Whether the operation was successful
        error: Exception if operation failed
        additional_context: Additional context information
    """
    try:
        user_context = await get_current_mcp_user()
        request_context = await get_current_mcp_request()

        log_data = {
            "operation": operation_name,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mcp_operation": True,  # Flag for MCP-specific operations
        }

        if user_context:
            log_data["user"] = user_context.to_dict()

        if request_context:
            log_data["request"] = request_context.to_dict()

        if error:
            log_data["error"] = {"type": type(error).__name__, "message": str(error)}

        if additional_context:
            log_data["additional_context"] = additional_context

        if success:
            logger.info("MCP operation completed: %s", operation_name, extra=log_data)
        else:
            logger.error("MCP operation failed: %s", operation_name, extra=log_data)

    except Exception as e:
        logger.error("Failed to log MCP operation: %s", e)


def generate_request_id() -> str:
    """
    Generate a unique request ID for MCP operations.

    Returns:
        Unique request identifier
    """
    return str(uuid.uuid4())


async def extract_client_info_from_request(request) -> Dict[str, Optional[str]]:
    """
    Extract client information from FastAPI request.

    Args:
        request: FastAPI Request object

    Returns:
        Dictionary with ip_address and user_agent
    """
    try:
        # Extract IP address using existing security manager patterns
        from ...managers.security_manager import security_manager

        ip_address = security_manager.get_client_ip(request)
        user_agent = security_manager.get_client_user_agent(request)

        return {"ip_address": ip_address, "user_agent": user_agent}
    except Exception as e:
        logger.warning("Failed to extract client info from request: %s", e)
        return {"ip_address": None, "user_agent": None}


async def create_mcp_audit_trail(
    operation: str,
    user_context: MCPUserContext,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    changes: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Create an audit trail entry for MCP operations.

    This function creates comprehensive audit logs for MCP operations
    using the existing logging infrastructure and patterns.

    Args:
        operation: Name of the operation being audited
        user_context: User context for the operation
        resource_type: Type of resource being operated on (optional)
        resource_id: ID of the resource being operated on (optional)
        changes: Dictionary of changes made (optional)
        metadata: Additional metadata for the audit entry (optional)
    """
    try:
        # Create audit entry using existing logging patterns
        audit_data = {
            "operation": operation,
            "user_id": user_context.user_id,
            "username": user_context.username,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mcp_operation": True,
            "ip_address": user_context.ip_address,
            "user_agent": user_context.user_agent,
            "token_type": user_context.token_type,
            "token_id": user_context.token_id,
        }

        if resource_type:
            audit_data["resource_type"] = resource_type

        if resource_id:
            audit_data["resource_id"] = resource_id

        if changes:
            audit_data["changes"] = changes

        if metadata:
            audit_data["metadata"] = metadata

        # Add request context if available
        try:
            request_context = get_mcp_request_context()
            audit_data["request_id"] = request_context.request_id
            audit_data["tool_name"] = request_context.tool_name
        except Exception:  # TODO: Use specific exception type
            pass  # Request context is optional

        # Log the audit entry
        logger.info(
            "MCP Audit: %s by user %s (%s)", operation, user_context.user_id, user_context.username, extra=audit_data
        )

    except Exception as e:
        logger.error("Failed to create MCP audit trail for operation %s: %s", operation, e)


async def validate_workspace_access(
    required_role: Optional[str] = None, user_context: Optional[MCPUserContext] = None
) -> bool:
    """
    Validate that the current user can access a specific workspace.

    Args:
        workspace_id: Workspace ID to check access for
        required_role: Required role in the workspace (None for any member)
        user_context: User context (uses current context if None)

    Returns:
        True if user can access the workspace, False otherwise
    """
    if user_context is None:
        user_context = await get_current_mcp_user()

    if user_context is None:
        return False

    # Check if user is a member of the workspace
    if not user_context.is_workspace_member(workspace_id):
        return False

    # If no specific role required, membership is sufficient
    if required_role is None:
        return True

    # Check role requirements
    user_role = user_context.get_workspace_role(workspace_id)
    if user_role == "owner":
        return True
    elif user_role == "admin" and required_role in ["admin", "member"]:
        return True
    elif user_role == "member" and required_role == "member":
        return True

    return False


async def require_workspace_access(
    workspace_id: str, required_role: Optional[str] = None, user_context: Optional[MCPUserContext] = None
) -> MCPUserContext:
    """
    Require that the current user can access a specific workspace.

    Args:
        workspace_id: Workspace ID to check access for
        required_role: Required role in the workspace (None for any member)
        user_context: User context (uses current context if None)

    Returns:
        MCPUserContext if access is granted

    Raises:
        MCPAuthenticationError: If no user context is available
        MCPAuthorizationError: If user cannot access the workspace
    """
    if user_context is None:
        user_context = await get_current_mcp_user()

    if user_context is None:
        raise MCPAuthenticationError("Authentication required for workspace access")

    if not await validate_workspace_access(workspace_id, required_role, user_context):
        user_role = user_context.get_workspace_role(workspace_id)
        raise MCPAuthorizationError(
            f"Insufficient access to workspace {workspace_id}",
            context={
                "workspace_id": workspace_id,
                "required_role": required_role,
                "user_role": user_role,
                "is_member": user_context.is_workspace_member(workspace_id),
            },
        )

    return user_context
