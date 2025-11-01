"""
Base AI Agent

This module provides the base class for all AI agents in the orchestration system.
All specialized agents inherit from this base class to ensure consistent behavior
and integration with existing Second Brain Database systems.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncGenerator, Protocol
from datetime import datetime, timezone, timedelta
import uuid

from ..models.events import AIEvent, EventType
from ....integrations.mcp.context import MCPUserContext, get_current_mcp_user
from ....managers.logging_manager import get_logger
from ....config import settings

logger = get_logger(prefix="[BaseAgent]")


class AgentCapability(Protocol):
    """Protocol for agent capabilities."""
    name: str
    description: str
    required_permissions: List[str]


class BaseAgent(ABC):
    """
    Base class for all AI agents in the orchestration system.
    
    Provides common functionality for:
    - Session management and context handling
    - MCP tool integration and security
    - Event streaming and communication
    - Error handling and recovery
    - Performance monitoring and logging
    """
    
    def __init__(self, agent_type: str, orchestrator=None):
        """
        Initialize the base agent.
        
        Args:
            agent_type: Type identifier for this agent
            orchestrator: Reference to the agent orchestrator
        """
        self.agent_type = agent_type
        self.orchestrator = orchestrator
        self.logger = get_logger(prefix=f"[{agent_type.title()}Agent]")
        self.capabilities: List[AgentCapability] = []
        self.active_sessions: Dict[str, Any] = {}
        
    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Human-readable name for this agent."""
        pass
    
    @property
    @abstractmethod
    def agent_description(self) -> str:
        """Description of what this agent does."""
        pass
    
    @abstractmethod
    async def handle_request(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[AIEvent, None]:
        """
        Handle a user request and generate streaming responses.
        
        Args:
            session_id: AI session identifier
            request: User's request text
            user_context: MCP user context for authentication and permissions
            metadata: Additional request metadata
            
        Yields:
            AIEvent objects for streaming to the frontend
        """
        pass
    
    @abstractmethod
    async def get_capabilities(self, user_context: MCPUserContext) -> List[Dict[str, Any]]:
        """
        Get list of capabilities available to the user.
        
        Args:
            user_context: MCP user context for permission checking
            
        Returns:
            List of capability dictionaries
        """
        pass
    
    async def initialize_session(
        self, 
        session_id: str, 
        user_context: MCPUserContext
    ) -> Dict[str, Any]:
        """
        Initialize a new session with enhanced security validation.
        
        Args:
            session_id: AI session identifier
            user_context: MCP user context
            
        Returns:
            Session initialization data
        """
        # Enhanced session security validation
        await self._validate_session_security(session_id, user_context)
        
        # Generate session security token
        import secrets
        session_token = secrets.token_urlsafe(32)
        
        session_data = {
            "session_id": session_id,
            "agent_type": self.agent_type,
            "user_id": user_context.user_id,
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
            "security_token": session_token,
            "ip_address": getattr(user_context, 'ip_address', 'unknown'),
            "user_agent": getattr(user_context, 'user_agent', 'unknown'),
            "context": {},
            "conversation_history": [],
            "metadata": {
                "security_level": "standard",
                "max_conversation_length": 10000,
                "max_tool_calls": 100,
                "rate_limit_remaining": 1000
            }
        }
        
        self.active_sessions[session_id] = session_data
        
        # Log session creation
        await self._log_session_event(session_id, user_context, "session_created")
        
        self.logger.info(
            "Initialized secure %s session %s for user %s",
            self.agent_type, session_id, user_context.user_id
        )
        
        return session_data
    
    async def _validate_session_security(self, session_id: str, user_context: MCPUserContext) -> None:
        """Validate session security requirements."""
        # Check for session ID format
        if not session_id or len(session_id) < 16:
            raise ValueError("Invalid session ID format")
        
        # Check for concurrent session limits
        user_sessions = [
            s for s in self.active_sessions.values() 
            if s.get("user_id") == user_context.user_id
        ]
        
        if len(user_sessions) >= 5:  # Max 5 concurrent sessions per user
            raise ValueError("Maximum concurrent sessions exceeded")
        
        # Validate user context integrity
        if not user_context.user_id or not user_context.username:
            raise ValueError("Invalid user context")
    
    async def _log_session_event(
        self, 
        session_id: str, 
        user_context: MCPUserContext, 
        event_type: str
    ) -> None:
        """Log session-related security events."""
        try:
            from ..security.ai_security_manager import ai_security_manager, ConversationPrivacyMode
            
            await ai_security_manager.log_ai_audit_event(
                user_context=user_context,
                session_id=session_id,
                event_type="session_management",
                agent_type=self.agent_type,
                action=event_type,
                details={
                    "session_id": session_id,
                    "agent_type": self.agent_type,
                    "active_sessions_count": len(self.active_sessions)
                },
                privacy_mode=ConversationPrivacyMode.PRIVATE,
                success=True
            )
        except Exception as e:
            self.logger.error("Failed to log session event: %s", e)
    
    async def cleanup_session(self, session_id: str) -> None:
        """
        Clean up resources for a session with security validation.
        
        Args:
            session_id: AI session identifier
        """
        if session_id in self.active_sessions:
            session_data = self.active_sessions.pop(session_id)
            
            # Secure cleanup - clear sensitive data
            if "security_token" in session_data:
                session_data["security_token"] = "[CLEARED]"
            
            # Log session cleanup for audit
            try:
                from ..security.ai_security_manager import ai_security_manager, ConversationPrivacyMode
                from ....integrations.mcp.context import MCPUserContext
                
                # Create minimal user context for logging
                user_context = MCPUserContext(
                    user_id=session_data.get("user_id", "unknown"),
                    username="",
                    permissions=[]
                )
                
                await ai_security_manager.log_ai_audit_event(
                    user_context=user_context,
                    session_id=session_id,
                    event_type="session_management",
                    agent_type=self.agent_type,
                    action="session_cleanup",
                    details={
                        "session_duration_minutes": self._calculate_session_duration(session_data),
                        "conversation_messages": len(session_data.get("conversation_history", [])),
                        "cleanup_reason": "normal_cleanup"
                    },
                    privacy_mode=ConversationPrivacyMode.PRIVATE,
                    success=True
                )
            except Exception as e:
                self.logger.error("Failed to log session cleanup: %s", e)
            
            self.logger.info(
                "Cleaned up secure %s session %s for user %s",
                self.agent_type, session_id, session_data.get("user_id")
            )
    
    def _calculate_session_duration(self, session_data: Dict[str, Any]) -> float:
        """Calculate session duration in minutes."""
        try:
            created_at = session_data.get("created_at")
            if isinstance(created_at, datetime):
                duration = datetime.now(timezone.utc) - created_at
                return duration.total_seconds() / 60
        except Exception:
            pass
        return 0.0
    
    async def emit_event(
        self, 
        session_id: str, 
        event_type: EventType, 
        data: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AIEvent:
        """
        Create and emit an AI event.
        
        Args:
            session_id: AI session identifier
            event_type: Type of event to emit
            data: Event data payload
            metadata: Additional event metadata
            
        Returns:
            Created AIEvent
        """
        event = AIEvent(
            type=event_type,
            data=data,
            session_id=session_id,
            agent_type=self.agent_type,
            metadata=metadata or {}
        )
        
        # If orchestrator is available, emit through it
        if self.orchestrator and hasattr(self.orchestrator, 'event_bus'):
            await self.orchestrator.event_bus.emit_event(event)
        
        return event
    
    async def emit_token(self, session_id: str, token: str) -> AIEvent:
        """Emit a streaming token event."""
        return await self.emit_event(
            session_id, 
            EventType.TOKEN, 
            {"token": token}
        )
    
    async def emit_response(self, session_id: str, response: str) -> AIEvent:
        """Emit a complete response event."""
        return await self.emit_event(
            session_id, 
            EventType.RESPONSE, 
            {"response": response}
        )
    
    async def emit_tool_call(
        self, 
        session_id: str, 
        tool_name: str, 
        parameters: Dict[str, Any]
    ) -> AIEvent:
        """Emit a tool call event."""
        return await self.emit_event(
            session_id, 
            EventType.TOOL_CALL, 
            {"tool_name": tool_name, "parameters": parameters},
            metadata={"tool_name": tool_name}
        )
    
    async def emit_tool_result(
        self, 
        session_id: str, 
        tool_name: str, 
        result: Any
    ) -> AIEvent:
        """Emit a tool result event."""
        return await self.emit_event(
            session_id, 
            EventType.TOOL_RESULT, 
            {"tool_name": tool_name, "result": result},
            metadata={"tool_name": tool_name}
        )
    
    async def emit_status(
        self, 
        session_id: str, 
        status: EventType, 
        message: Optional[str] = None
    ) -> AIEvent:
        """Emit a status event (thinking, typing, waiting)."""
        data = {"status": status.value}
        if message:
            data["message"] = message
            
        return await self.emit_event(session_id, status, data)
    
    async def emit_error(
        self, 
        session_id: str, 
        error_message: str, 
        error_code: Optional[str] = None
    ) -> AIEvent:
        """Emit an error event."""
        return await self.emit_event(
            session_id, 
            EventType.ERROR, 
            {"error": error_message, "error_code": error_code}
        )
    
    async def execute_mcp_tool(
        self, 
        session_id: str,
        tool_name: str, 
        parameters: Dict[str, Any], 
        user_context: MCPUserContext
    ) -> Any:
        """
        Execute an MCP tool with enhanced security validation and monitoring.
        
        Args:
            session_id: AI session identifier
            tool_name: Name of the MCP tool to execute
            parameters: Tool parameters
            user_context: MCP user context
            
        Returns:
            Tool execution result
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Enhanced security validation
            await self._validate_tool_execution_security(tool_name, parameters, user_context)
            
            # Emit tool call event
            await self.emit_tool_call(session_id, tool_name, parameters)
            
            # Execute tool through orchestrator if available
            if self.orchestrator and hasattr(self.orchestrator, 'tool_coordinator'):
                result = await self.orchestrator.tool_coordinator.execute_tool(
                    tool_name, parameters, user_context
                )
            else:
                # Fallback: direct tool execution (would need MCP client)
                self.logger.warning(
                    "No orchestrator available for tool execution: %s", tool_name
                )
                result = {"error": "Tool execution not available"}
            
            # Log successful tool execution
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            await self._log_tool_execution(
                session_id, tool_name, parameters, user_context, 
                result, True, execution_time
            )
            
            # Emit tool result event
            await self.emit_tool_result(session_id, tool_name, result)
            
            return result
            
        except Exception as e:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            # Log failed tool execution
            await self._log_tool_execution(
                session_id, tool_name, parameters, user_context, 
                None, False, execution_time, str(e)
            )
            
            self.logger.error("Tool execution failed: %s - %s", tool_name, e)
            await self.emit_error(session_id, f"Tool execution failed: {str(e)}")
            raise
    
    async def _validate_tool_execution_security(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any], 
        user_context: MCPUserContext
    ) -> None:
        """Validate tool execution security requirements."""
        # Check for dangerous tool patterns
        dangerous_tools = ["delete", "remove", "destroy", "admin", "system"]
        if any(danger in tool_name.lower() for danger in dangerous_tools):
            # Require elevated permissions for dangerous operations
            if not user_context.has_permission("admin:tools"):
                raise PermissionError(f"Elevated permissions required for tool: {tool_name}")
        
        # Validate parameter safety
        if parameters:
            await self._validate_tool_parameters(parameters)
    
    async def _validate_tool_parameters(self, parameters: Dict[str, Any]) -> None:
        """Validate tool parameters for security issues."""
        # Check for injection patterns in string parameters
        dangerous_patterns = [
            r"<script", r"javascript:", r"eval\(", r"exec\(", 
            r"system\(", r"shell_exec", r"passthru", r"file_get_contents"
        ]
        
        import re
        for key, value in parameters.items():
            if isinstance(value, str):
                for pattern in dangerous_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        raise ValueError(f"Potentially dangerous content in parameter {key}")
    
    async def _log_tool_execution(
        self,
        session_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        user_context: MCPUserContext,
        result: Any,
        success: bool,
        execution_time_ms: float,
        error_message: str = None
    ) -> None:
        """Log tool execution for security monitoring."""
        try:
            from ..security.ai_security_manager import ai_security_manager, ConversationPrivacyMode
            
            # Sanitize parameters for logging (remove sensitive data)
            safe_parameters = {
                k: v if k.lower() not in ['password', 'token', 'secret', 'key'] else '[REDACTED]'
                for k, v in parameters.items()
            }
            
            await ai_security_manager.log_ai_audit_event(
                user_context=user_context,
                session_id=session_id,
                event_type="tool_execution",
                agent_type=self.agent_type,
                action=f"execute_{tool_name}",
                details={
                    "tool_name": tool_name,
                    "parameters": safe_parameters,
                    "execution_time_ms": execution_time_ms,
                    "result_type": type(result).__name__ if result else None,
                    "parameter_count": len(parameters)
                },
                privacy_mode=ConversationPrivacyMode.PRIVATE,
                success=success,
                error_message=error_message
            )
        except Exception as e:
            self.logger.error("Failed to log tool execution: %s", e)
    
    async def generate_ai_response(
        self, 
        session_id: str,
        prompt: str, 
        context: Optional[Dict[str, Any]] = None,
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Generate AI response using the model engine.
        
        Args:
            session_id: AI session identifier
            prompt: Input prompt for the AI model
            context: Additional context for the response
            stream: Whether to stream the response
            
        Yields:
            Response tokens or complete response
        """
        try:
            # Emit thinking status
            await self.emit_status(session_id, EventType.THINKING)
            
            # Generate response through orchestrator if available
            if self.orchestrator and hasattr(self.orchestrator, 'model_engine'):
                if stream:
                    await self.emit_status(session_id, EventType.TYPING)
                    async for token in self.orchestrator.model_engine.generate_response(
                        prompt, stream=True
                    ):
                        await self.emit_token(session_id, token)
                        yield token
                else:
                    response = await self.orchestrator.model_engine.generate_response(
                        prompt, stream=False
                    )
                    await self.emit_response(session_id, response)
                    yield response
            else:
                # Fallback response
                fallback_response = f"I'm a {self.agent_name} but I don't have access to the AI model right now."
                await self.emit_response(session_id, fallback_response)
                yield fallback_response
                
        except Exception as e:
            self.logger.error("AI response generation failed: %s", e)
            await self.emit_error(session_id, f"AI response generation failed: {str(e)}")
            raise
    
    async def load_user_context(self, user_context: MCPUserContext) -> Dict[str, Any]:
        """
        Load relevant context for the user.
        
        Args:
            user_context: MCP user context
            
        Returns:
            Dictionary containing user context data
        """
        context = {
            "user_id": user_context.user_id,
            "username": user_context.username,
            "role": user_context.role,
            "permissions": user_context.permissions
        }
        
        # Add family context if available
        if user_context.family_memberships:
            context["families"] = [
                {
                    "family_id": fm.get("family_id"),
                    "role": fm.get("role")
                }
                for fm in user_context.family_memberships
            ]
        
        # Add workspace context if available
        if user_context.workspaces:
            context["workspaces"] = [
                {
                    "workspace_id": ws.get("_id"),
                    "name": ws.get("name"),
                    "role": ws.get("role")
                }
                for ws in user_context.workspaces
            ]
        
        return context
    
    async def validate_permissions(
        self, 
        user_context: MCPUserContext, 
        required_permissions: List[str]
    ) -> bool:
        """
        Validate that the user has required permissions with enhanced security checks.
        
        Args:
            user_context: MCP user context
            required_permissions: List of required permissions
            
        Returns:
            True if user has all required permissions
        """
        if not required_permissions:
            return True
        
        # Enhanced validation with security logging
        has_permissions = user_context.has_all_permissions(required_permissions)
        
        if not has_permissions:
            self.logger.warning(
                "Permission denied for user %s: required %s, has %s",
                user_context.user_id, required_permissions, user_context.permissions
            )
            
            # Log security event for audit trail
            if hasattr(self, 'orchestrator') and self.orchestrator:
                try:
                    from ..security.ai_security_manager import ai_security_manager, ConversationPrivacyMode
                    await ai_security_manager.log_ai_audit_event(
                        user_context=user_context,
                        session_id="",
                        event_type="permission_check",
                        agent_type=self.agent_type,
                        action="permission_denied",
                        details={
                            "required_permissions": required_permissions,
                            "user_permissions": user_context.permissions,
                            "agent_type": self.agent_type
                        },
                        privacy_mode=ConversationPrivacyMode.PRIVATE,
                        success=False,
                        error_message=f"Missing permissions: {set(required_permissions) - set(user_context.permissions)}"
                    )
                except Exception as e:
                    self.logger.error("Failed to log permission denial: %s", e)
        
        return has_permissions
    
    def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data for a session ID."""
        return self.active_sessions.get(session_id)
    
    def update_session_context(
        self, 
        session_id: str, 
        context_updates: Dict[str, Any]
    ) -> None:
        """Update session context with new data."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["context"].update(context_updates)
    
    def add_to_conversation_history(
        self, 
        session_id: str, 
        role: str, 
        content: str
    ) -> None:
        """Add a message to the conversation history."""
        if session_id in self.active_sessions:
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self.active_sessions[session_id]["conversation_history"].append(message)
    
    async def classify_request_intent(self, request: str) -> Dict[str, Any]:
        """
        Classify the intent of a user request with security analysis.
        
        Args:
            request: User's request text
            
        Returns:
            Dictionary with intent classification and security assessment
        """
        # Security validation first
        security_analysis = await self._analyze_request_security(request)
        
        # Basic intent classification - can be enhanced with ML models
        request_lower = request.lower()
        
        # Common intent patterns
        intent_data = {"confidence": 0.5, "intent": "general"}
        
        if any(word in request_lower for word in ["create", "make", "new", "add"]):
            intent_data = {"intent": "create", "confidence": 0.8}
        elif any(word in request_lower for word in ["show", "list", "get", "find", "search"]):
            intent_data = {"intent": "retrieve", "confidence": 0.8}
        elif any(word in request_lower for word in ["update", "change", "modify", "edit"]):
            intent_data = {"intent": "update", "confidence": 0.8}
        elif any(word in request_lower for word in ["delete", "remove", "cancel"]):
            intent_data = {"intent": "delete", "confidence": 0.8}
        elif any(word in request_lower for word in ["help", "how", "what", "explain"]):
            intent_data = {"intent": "help", "confidence": 0.9}
        
        # Add security analysis to response
        intent_data.update({
            "security_analysis": security_analysis,
            "request_length": len(request),
            "word_count": len(request.split()),
            "requires_elevated_permissions": security_analysis.get("risk_level") == "high"
        })
        
        return intent_data
    
    async def _analyze_request_security(self, request: str) -> Dict[str, Any]:
        """Analyze request for security risks."""
        import re
        
        security_issues = []
        risk_level = "low"
        
        # Check for injection patterns
        injection_patterns = [
            r"<script", r"javascript:", r"eval\(", r"exec\(", 
            r"system\(", r"shell_exec", r"\.\.\/", r"file://",
            r"ignore\s+(?:previous|all)\s+instructions",
            r"system\s*:\s*you\s+are\s+now",
            r"forget\s+everything\s+above",
            r"reveal\s+secrets?",
            r"bypass\s+security",
            r"admin\s+access"
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, request, re.IGNORECASE):
                security_issues.append(f"potential_injection_{pattern[:10]}")
                risk_level = "high"
        
        # Check for excessive length
        if len(request) > 5000:
            security_issues.append("excessive_length")
            risk_level = "medium" if risk_level == "low" else risk_level
        
        # Check for repetitive patterns (potential DoS)
        words = request.split()
        if len(words) > 10:
            word_counts = {}
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1
            
            max_repetition = max(word_counts.values()) if word_counts else 0
            if max_repetition > len(words) * 0.3:
                security_issues.append("excessive_repetition")
                risk_level = "medium" if risk_level == "low" else risk_level
        
        # Check for sensitive data patterns
        sensitive_patterns = [
            r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # Credit card
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
            r"password\s*(?:is|:|\=)\s*\w+",  # Password
            r"token\s*(?:is|:|\=)\s*\w+",  # Token
            r"secret\s*(?:is|:|\=)\s*\w+",  # Secret
            r"key\s*(?:is|:|\=)\s*\w+"  # Key
        ]
        
        for pattern in sensitive_patterns:
            if re.search(pattern, request, re.IGNORECASE):
                security_issues.append("sensitive_data_detected")
                risk_level = "high"
        
        return {
            "risk_level": risk_level,
            "security_issues": security_issues,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "safe_for_processing": len(security_issues) == 0
        }