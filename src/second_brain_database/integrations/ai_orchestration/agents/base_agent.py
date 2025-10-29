"""
Base AI Agent

This module provides the base class for all AI agents in the orchestration system.
All specialized agents inherit from this base class to ensure consistent behavior
and integration with existing Second Brain Database systems.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncGenerator, Protocol
from datetime import datetime, timezone
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
        Initialize a new session for this agent.
        
        Args:
            session_id: AI session identifier
            user_context: MCP user context
            
        Returns:
            Session initialization data
        """
        session_data = {
            "session_id": session_id,
            "agent_type": self.agent_type,
            "user_id": user_context.user_id,
            "created_at": datetime.now(timezone.utc),
            "context": {},
            "conversation_history": [],
            "metadata": {}
        }
        
        self.active_sessions[session_id] = session_data
        
        self.logger.info(
            "Initialized %s session %s for user %s",
            self.agent_type, session_id, user_context.user_id
        )
        
        return session_data
    
    async def cleanup_session(self, session_id: str) -> None:
        """
        Clean up resources for a session.
        
        Args:
            session_id: AI session identifier
        """
        if session_id in self.active_sessions:
            session_data = self.active_sessions.pop(session_id)
            self.logger.info(
                "Cleaned up %s session %s for user %s",
                self.agent_type, session_id, session_data.get("user_id")
            )
    
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
        Execute an MCP tool with proper context and error handling.
        
        Args:
            session_id: AI session identifier
            tool_name: Name of the MCP tool to execute
            parameters: Tool parameters
            user_context: MCP user context
            
        Returns:
            Tool execution result
        """
        try:
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
            
            # Emit tool result event
            await self.emit_tool_result(session_id, tool_name, result)
            
            return result
            
        except Exception as e:
            self.logger.error("Tool execution failed: %s - %s", tool_name, e)
            await self.emit_error(session_id, f"Tool execution failed: {str(e)}")
            raise
    
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
        Validate that the user has required permissions.
        
        Args:
            user_context: MCP user context
            required_permissions: List of required permissions
            
        Returns:
            True if user has all required permissions
        """
        if not required_permissions:
            return True
            
        return user_context.has_all_permissions(required_permissions)
    
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
        Classify the intent of a user request.
        
        Args:
            request: User's request text
            
        Returns:
            Dictionary with intent classification
        """
        # Basic intent classification - can be enhanced with ML models
        request_lower = request.lower()
        
        # Common intent patterns
        if any(word in request_lower for word in ["create", "make", "new", "add"]):
            return {"intent": "create", "confidence": 0.8}
        elif any(word in request_lower for word in ["show", "list", "get", "find", "search"]):
            return {"intent": "retrieve", "confidence": 0.8}
        elif any(word in request_lower for word in ["update", "change", "modify", "edit"]):
            return {"intent": "update", "confidence": 0.8}
        elif any(word in request_lower for word in ["delete", "remove", "cancel"]):
            return {"intent": "delete", "confidence": 0.8}
        elif any(word in request_lower for word in ["help", "how", "what", "explain"]):
            return {"intent": "help", "confidence": 0.9}
        else:
            return {"intent": "general", "confidence": 0.5}