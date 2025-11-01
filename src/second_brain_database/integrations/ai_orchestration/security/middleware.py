"""
AI Security Middleware

This module provides middleware for AI routes that integrates with existing
security systems and adds AI-specific security validation.
"""

from typing import Callable, Dict, Any, Optional
from datetime import datetime, timezone
import json

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse

from ....managers.logging_manager import get_logger
from ....integrations.mcp.context import MCPUserContext
from .ai_security_manager import ai_security_manager, AIPermission, ConversationPrivacyMode
from .security_integration import ai_security_integration

logger = get_logger(prefix="[AISecurityMiddleware]")


class AISecurityMiddleware:
    """
    Middleware for AI routes that provides comprehensive security validation.
    """
    
    def __init__(self, app):
        self.app = app
        self.logger = logger
        
        # Paths that require AI security validation
        self.ai_paths = [
            "/ai/sessions",
            "/ai/ws/",
            "/ai/performance/",
            "/ai/stats"
        ]
        
        # Permission mapping for different AI operations
        self.operation_permissions = {
            "create_session": AIPermission.BASIC_CHAT,
            "send_message": AIPermission.BASIC_CHAT,
            "voice_interaction": AIPermission.VOICE_INTERACTION,
            "family_management": AIPermission.FAMILY_MANAGEMENT,
            "workspace_collaboration": AIPermission.WORKSPACE_COLLABORATION,
            "commerce_assistance": AIPermission.COMMERCE_ASSISTANCE,
            "security_monitoring": AIPermission.SECURITY_MONITORING,
            "admin_operations": AIPermission.ADMIN_OPERATIONS
        }

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through AI security middleware.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/route handler
            
        Returns:
            Response object
        """
        # Check if this is an AI-related request
        if not self._is_ai_request(request):
            return await call_next(request)
        
        try:
            # Extract user context from request
            user_context = await self._extract_user_context(request)
            if not user_context:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"error": "Authentication required for AI operations"}
                )
            
            # Determine operation type and required permissions
            operation_type = self._determine_operation_type(request)
            agent_type = self._extract_agent_type(request)
            session_id = self._extract_session_id(request)
            
            # Extract request data for validation
            request_data = await self._extract_request_data(request)
            
            # Perform comprehensive security validation
            await ai_security_integration.validate_ai_request(
                request=request,
                user_context=user_context,
                operation_type=operation_type,
                agent_type=agent_type,
                session_id=session_id or "",
                request_data=request_data
            )
            
            # Add security headers to request for downstream processing
            request.state.ai_security_validated = True
            request.state.user_context = user_context
            request.state.operation_type = operation_type
            request.state.agent_type = agent_type
            
            # Process request
            response = await call_next(request)
            
            # Log successful request
            await self._log_successful_request(
                request, user_context, operation_type, agent_type, session_id
            )
            
            return response
            
        except HTTPException as e:
            # Log security violation
            await self._log_security_violation(request, str(e.detail), e.status_code)
            raise
            
        except Exception as e:
            # Log unexpected error
            self.logger.error(
                "Unexpected error in AI security middleware: %s", str(e), exc_info=True
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Internal security validation error"}
            )

    def _is_ai_request(self, request: Request) -> bool:
        """Check if request is AI-related."""
        path = request.url.path
        return any(ai_path in path for ai_path in self.ai_paths)

    async def _extract_user_context(self, request: Request) -> Optional[MCPUserContext]:
        """Extract user context from request."""
        try:
            # Try to get user from request state (set by auth middleware)
            if hasattr(request.state, 'current_user'):
                user = request.state.current_user
                return MCPUserContext(
                    user_id=str(user.get("_id", "")),
                    username=user.get("username", ""),
                    permissions=user.get("permissions", [])
                )
            
            # Try to extract from headers (for WebSocket connections)
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                # This would integrate with existing JWT validation
                # For now, return None to indicate authentication required
                pass
            
            return None
            
        except Exception as e:
            self.logger.error("Error extracting user context: %s", str(e))
            return None

    def _determine_operation_type(self, request: Request) -> str:
        """Determine the type of AI operation from request."""
        path = request.url.path
        method = request.method
        
        if "/sessions" in path and method == "POST":
            return "create_session"
        elif "/sessions/" in path and "/message" in path:
            return "send_message"
        elif "/voice/" in path:
            return "voice_interaction"
        elif "/ws/" in path:
            return "websocket_connection"
        elif "/stats" in path or "/performance/" in path:
            return "monitoring"
        else:
            return "general_ai_operation"

    def _extract_agent_type(self, request: Request) -> str:
        """Extract agent type from request."""
        try:
            # Try to get from path parameters
            path_parts = request.url.path.split("/")
            if "agent" in request.query_params:
                return request.query_params["agent"]
            
            # Try to get from request body (for POST requests)
            if hasattr(request.state, 'body_data'):
                body_data = request.state.body_data
                if isinstance(body_data, dict) and "agent_type" in body_data:
                    return body_data["agent_type"]
            
            return "personal"  # Default agent type
            
        except Exception:
            return "personal"

    def _extract_session_id(self, request: Request) -> Optional[str]:
        """Extract session ID from request."""
        try:
            path_parts = request.url.path.split("/")
            
            # Look for session ID in path
            for i, part in enumerate(path_parts):
                if part == "sessions" and i + 1 < len(path_parts):
                    return path_parts[i + 1]
                elif part == "ws" and i + 1 < len(path_parts):
                    return path_parts[i + 1]
            
            # Look in query parameters
            if "session_id" in request.query_params:
                return request.query_params["session_id"]
            
            return None
            
        except Exception:
            return None

    async def _extract_request_data(self, request: Request) -> Dict[str, Any]:
        """Extract request data for security validation."""
        try:
            request_data = {
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "headers": {k: v for k, v in request.headers.items() if k.lower() not in ['authorization', 'cookie']},  # Exclude sensitive headers
                "client_ip": request.client.host if request.client else "",
                "user_agent": request.headers.get("user-agent", ""),
                "content_type": request.headers.get("content-type", ""),
                "content_length": request.headers.get("content-length", "0")
            }
            
            # Try to get request body for POST/PUT requests
            if request.method in ["POST", "PUT", "PATCH"]:
                try:
                    # Handle different content types safely
                    content_type = request.headers.get("content-type", "").lower()
                    
                    if hasattr(request.state, 'body_data'):
                        body_data = request.state.body_data
                        
                        # Sanitize sensitive data from body
                        if isinstance(body_data, dict):
                            sanitized_body = {
                                k: v for k, v in body_data.items() 
                                if k.lower() not in ['password', 'token', 'secret', 'key', 'auth']
                            }
                            request_data["body"] = sanitized_body
                        else:
                            # For non-dict bodies, just store metadata
                            request_data["body_type"] = type(body_data).__name__
                            request_data["body_size"] = len(str(body_data)) if body_data else 0
                            
                except Exception as e:
                    self.logger.debug("Could not extract body data: %s", str(e))
                    request_data["body_extraction_error"] = "Could not parse body"
            
            return request_data
            
        except Exception as e:
            self.logger.error("Error extracting request data: %s", str(e))
            return {}

    async def _log_successful_request(
        self,
        request: Request,
        user_context: MCPUserContext,
        operation_type: str,
        agent_type: str,
        session_id: Optional[str]
    ) -> None:
        """Log successful AI request."""
        try:
            await ai_security_manager.log_ai_audit_event(
                user_context=user_context,
                session_id=session_id or "",
                event_type="api_request",
                agent_type=agent_type,
                action=operation_type,
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "ip_address": request.client.host if request.client else "",
                    "user_agent": request.headers.get("user-agent", "")
                },
                privacy_mode=ConversationPrivacyMode.PRIVATE,
                request=request,
                success=True
            )
        except Exception as e:
            self.logger.error("Error logging successful request: %s", str(e))

    async def _log_security_violation(
        self,
        request: Request,
        error_message: str,
        status_code: int
    ) -> None:
        """Log security violation."""
        try:
            # Create minimal user context for logging
            user_context = MCPUserContext(
                user_id="unknown",
                username="",
                permissions=[]
            )
            
            await ai_security_manager.log_ai_audit_event(
                user_context=user_context,
                session_id="",
                event_type="security_violation",
                agent_type="security",
                action="request_blocked",
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "ip_address": request.client.host if request.client else "",
                    "user_agent": request.headers.get("user-agent", ""),
                    "status_code": status_code
                },
                privacy_mode=ConversationPrivacyMode.PRIVATE,
                request=request,
                success=False,
                error_message=error_message
            )
        except Exception as e:
            self.logger.error("Error logging security violation: %s", str(e))


def create_ai_security_middleware():
    """Create AI security middleware instance."""
    return AISecurityMiddleware