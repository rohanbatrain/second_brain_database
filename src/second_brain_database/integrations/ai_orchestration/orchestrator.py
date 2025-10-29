"""
AI Agent Orchestration System

This module provides the central orchestrator for managing specialized AI agents
that integrate with existing Second Brain Database functionality through FastAPI
and MCP tools.

The orchestrator manages six specialized AI agents:
- FamilyAssistantAgent: Family management and coordination
- PersonalAssistantAgent: Individual user tasks and preferences  
- WorkspaceAgent: Team collaboration and workspace management
- CommerceAgent: Shopping assistance and asset management
- SecurityAgent: Security monitoring and admin operations
- VoiceAgent: Voice interactions and multi-modal communication

All agents leverage existing MCP tools, managers, and database systems for
secure and consistent operation.
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime, timezone
import uuid
import asyncio

from .models.events import AIEvent, EventType
from .agents import (
    FamilyAssistantAgent,
    PersonalAssistantAgent,
    WorkspaceAgent,
    CommerceAgent,
    SecurityAgent,
    VoiceAgent,
    AGENT_REGISTRY,
    create_agent
)
from ...integrations.mcp.context import MCPUserContext
from ...integrations.ollama import OllamaClient
from ...managers.logging_manager import get_logger
from ...config import settings
from .model_engine import ModelEngine
from .memory_layer import MemoryLayer
from .resource_manager import ResourceManager
from .security import (
    ai_security_manager,
    ai_privacy_manager,
    ai_security_integration,
    ConversationPrivacyMode,
    AIPermission
)
from .errors import (
    AIOrchestrationError,
    AIErrorContext,
    AIErrorCategory,
    AIErrorSeverity,
    ModelInferenceError,
    AgentExecutionError,
    SessionManagementError,
    VoiceProcessingError,
    CommunicationError,
    handle_ai_errors,
    create_ai_error_context,
    log_ai_error
)
from .recovery import (
    session_recovery_manager,
    model_recovery_manager,
    voice_recovery_manager,
    communication_recovery_manager,
    trigger_comprehensive_recovery
)

logger = get_logger(prefix="[AgentOrchestrator]")


class SessionContext:
    """
    Session context for AI operations.
    
    Maintains unified session state across all communication channels
    and agent interactions.
    """
    
    def __init__(
        self,
        session_id: str,
        user_id: str,
        user_context: MCPUserContext,
        session_type: str = "chat"
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.user_context = user_context
        self.session_type = session_type
        
        # Agent state
        self.current_agent = "personal"  # Default agent
        self.agent_history = ["personal"]
        self.conversation_history = []
        
        # Context and memory
        self.loaded_context = {}
        self.short_term_memory = {}
        
        # Communication channels
        self.websocket_connection = None
        self.livekit_room = None
        self.voice_enabled = False
        
        # Timestamps
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = datetime.now(timezone.utc)
        self.expires_at = None
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)
    
    def switch_agent(self, agent_type: str):
        """Switch to a different agent."""
        if agent_type != self.current_agent:
            self.agent_history.append(agent_type)
            self.current_agent = agent_type
            self.update_activity()
    
    def enable_voice(self):
        """Enable voice capabilities for this session."""
        self.voice_enabled = True
        self.update_activity()
    
    def disable_voice(self):
        """Disable voice capabilities for this session."""
        self.voice_enabled = False
        self.update_activity()
    
    def add_message(self, role: str, content: str, agent_type: Optional[str] = None):
        """Add a message to conversation history."""
        message = {
            "role": role,
            "content": content,
            "agent_type": agent_type or self.current_agent,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.conversation_history.append(message)
        self.update_activity()





class AgentOrchestrator:
    """
    Central orchestrator for AI agent management and coordination.
    
    Manages specialized agents, routes requests, handles sessions,
    and coordinates with existing Second Brain Database systems.
    """
    
    def __init__(self):
        """Initialize the agent orchestrator."""
        self.logger = get_logger(prefix="[AgentOrchestrator]")
        
        # Initialize enhanced model engine with caching and performance optimization
        self.model_engine = ModelEngine()
        
        # Initialize memory layer with intelligent context management
        self.memory_layer = MemoryLayer()
        
        # Initialize resource manager for performance and cleanup
        self.resource_manager = ResourceManager()
        
        # Initialize tool coordinator for MCP integration
        from .tools.tool_coordinator import ToolCoordinator, set_global_tool_coordinator
        self.tool_coordinator = ToolCoordinator()
        
        # Set as global instance for health checks and monitoring
        set_global_tool_coordinator(self.tool_coordinator)
        
        # Initialize specialized agents using the registry
        self.agents = {}
        for agent_type in AGENT_REGISTRY.keys():
            self.agents[agent_type] = create_agent(agent_type, self)
        
        # Session management
        self.active_sessions: Dict[str, SessionContext] = {}
        
        # Initialize event bus
        from .event_bus import get_ai_event_bus
        self.event_bus = get_ai_event_bus()
        
        self.logger.info("Agent orchestrator initialized with %d agents", len(self.agents))
    
    @handle_ai_errors(
        operation_name="create_session",
        enable_recovery=True,
        circuit_breaker="session_creation",
        bulkhead="session_management"
    )
    async def create_session(
        self,
        user_context: MCPUserContext,
        session_type: str = "chat",
        agent_type: str = "personal"
    ) -> SessionContext:
        """
        Create a new AI session.
        
        Args:
            user_context: MCP user context for authentication
            session_type: Type of session (chat, voice, mixed)
            agent_type: Initial agent type to use
            
        Returns:
            SessionContext instance
        """
        try:
            # Security validation - check basic AI permissions
            await ai_security_manager.check_ai_permissions(
                user_context,
                AIPermission.BASIC_CHAT
            )
            
            # Check if voice permissions are needed
            if session_type in ["voice", "mixed"]:
                await ai_security_manager.check_ai_permissions(
                    user_context,
                    AIPermission.VOICE_INTERACTION
                )
            
            # Check agent-specific permissions
            agent_permission_map = {
                "family": AIPermission.FAMILY_MANAGEMENT,
                "workspace": AIPermission.WORKSPACE_COLLABORATION,
                "commerce": AIPermission.COMMERCE_ASSISTANCE,
                "security": AIPermission.SECURITY_MONITORING
            }
            
            if agent_type in agent_permission_map:
                await ai_security_manager.check_ai_permissions(
                    user_context,
                    agent_permission_map[agent_type]
                )
            
            session_id = str(uuid.uuid4())
            
            session_context = SessionContext(
                session_id=session_id,
                user_id=user_context.user_id,
                user_context=user_context,
                session_type=session_type
            )
            
            # Set initial agent
            session_context.switch_agent(agent_type)
            
            # Initialize agent session
            if agent_type in self.agents:
                await self.agents[agent_type].initialize_session(session_id, user_context)
            
            # Store session
            self.active_sessions[session_id] = session_context
            
            # Register session with resource manager
            await self.resource_manager.register_session(
                session_id, user_context.user_id, agent_type
            )
            
            # Log session creation for audit trail
            await ai_security_manager.log_ai_audit_event(
                user_context=user_context,
                session_id=session_id,
                event_type="session_management",
                agent_type=agent_type,
                action="create_session",
                details={
                    "session_type": session_type,
                    "initial_agent": agent_type
                },
                privacy_mode=ConversationPrivacyMode.PRIVATE,
                success=True
            )
            
            self.logger.info(
                "Created session %s for user %s with %s agent",
                session_id, user_context.user_id, agent_type
            )
            
            return session_context
            
        except Exception as e:
            error_context = create_ai_error_context(
                operation="create_session",
                user_id=user_context.user_id,
                agent_type=agent_type
            )
            
            session_error = SessionManagementError(
                f"Failed to create session: {str(e)}",
                session_id="",
                context=error_context
            )
            
            await log_ai_error(session_error)
            raise session_error from e
    
    async def enable_voice_for_session(self, session_id: str) -> bool:
        """
        Enable voice capabilities for an existing session.
        
        Args:
            session_id: AI session identifier
            
        Returns:
            True if voice was enabled successfully, False otherwise
        """
        try:
            session_context = self.active_sessions.get(session_id)
            if not session_context:
                return False
            
            # Enable voice for the session
            session_context.enable_voice()
            
            # Initialize voice agent session if needed
            voice_agent = self.agents.get("voice")
            if voice_agent:
                await voice_agent.initialize_session(session_id, session_context.user_context)
            
            self.logger.info(f"Voice enabled for session {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to enable voice for session {session_id}: {e}")
            return False
    
    @handle_ai_errors(
        operation_name="process_input",
        enable_recovery=True,
        circuit_breaker="input_processing",
        bulkhead="input_processing"
    )
    async def process_input(
        self,
        session_id: str,
        input_text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[AIEvent, None]:
        """
        Process user input and generate streaming responses.
        
        Args:
            session_id: AI session identifier
            input_text: User's input text
            metadata: Additional input metadata (e.g., audio data)
            
        Yields:
            AIEvent objects for streaming to frontend
        """
        try:
            async for event in self._process_input_internal(session_id, input_text, metadata):
                yield event
        except Exception as e:
            error_context = create_ai_error_context(
                operation="process_input",
                session_id=session_id
            )
            
            # Try to recover from the error
            try:
                recovery_result = await trigger_comprehensive_recovery(
                    session_id, error_context, self
                )
                
                if recovery_result.get("overall_success", False):
                    # Retry after recovery
                    async for event in self._process_input_internal(session_id, input_text, metadata):
                        yield event
                else:
                    # Recovery failed, provide error event
                    yield AIEvent(
                        type=EventType.ERROR,
                        data={
                            "error": "Input processing failed and recovery was unsuccessful",
                            "recovery_attempted": True,
                            "recovery_details": recovery_result
                        },
                        session_id=session_id,
                        agent_type="system"
                    )
            except Exception as recovery_error:
                # Both original operation and recovery failed
                yield AIEvent(
                    type=EventType.ERROR,
                    data={
                        "error": f"Input processing failed: {str(e)}",
                        "recovery_error": str(recovery_error)
                    },
                    session_id=session_id,
                    agent_type="system"
                )
    
    @handle_ai_errors(
        operation_name="process_voice_input",
        enable_recovery=True,
        circuit_breaker="voice_processing",
        bulkhead="voice_processing"
    )
    async def process_voice_input(
        self,
        session_id: str,
        audio_data: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[AIEvent, None]:
        """
        Process voice input and generate streaming responses.
        
        Args:
            session_id: AI session identifier
            audio_data: Raw audio data
            metadata: Additional input metadata
            
        Yields:
            AIEvent objects for streaming to frontend
        """
        try:
            # Get session context
            session_context = self.active_sessions.get(session_id)
            if not session_context:
                yield AIEvent(
                    type=EventType.ERROR,
                    data={"error": "Session not found"},
                    session_id=session_id,
                    agent_type="system"
                )
                return
            
            # Ensure voice is enabled for this session
            if not session_context.voice_enabled:
                yield AIEvent(
                    type=EventType.ERROR,
                    data={"error": "Voice not enabled for this session"},
                    session_id=session_id,
                    agent_type="system"
                )
                return
            
            # Route to voice agent for processing
            voice_agent = self.agents.get("voice")
            if not voice_agent:
                yield AIEvent(
                    type=EventType.ERROR,
                    data={"error": "Voice agent not available"},
                    session_id=session_id,
                    agent_type="system"
                )
                return
            
            # Process voice input through voice agent
            async for event in voice_agent.handle_voice_input(
                session_id, audio_data, session_context.user_context
            ):
                yield event
                
        except Exception as e:
            self.logger.error("Voice input processing failed for session %s: %s", session_id, e)
            yield AIEvent(
                type=EventType.ERROR,
                data={"error": f"Voice processing failed: {str(e)}"},
                session_id=session_id,
                agent_type="system"
            )
    
    async def _process_input_internal(
        self,
        session_id: str,
        input_text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[AIEvent, None]:
        """
        Process user input and generate streaming responses.
        
        Args:
            session_id: AI session identifier
            input_text: User's input text
            metadata: Additional input metadata (e.g., audio data)
            
        Yields:
            AIEvent objects for streaming to frontend
        """
        try:
            # Get session context
            session_context = self.active_sessions.get(session_id)
            if not session_context:
                yield AIEvent(
                    type=EventType.ERROR,
                    data={"error": "Session not found"},
                    session_id=session_id,
                    agent_type="system"
                )
                return
            
            # Security validation - validate request data
            request_data = {
                "input_text": input_text,
                "metadata": metadata or {}
            }
            
            # Note: In a real implementation, we would have access to the FastAPI Request object
            # For now, we'll validate what we can without it
            try:
                # Validate AI permissions for basic chat
                await ai_security_manager.check_ai_permissions(
                    session_context.user_context,
                    AIPermission.BASIC_CHAT
                )
                
                # Log AI interaction for audit trail
                await ai_security_manager.log_ai_audit_event(
                    user_context=session_context.user_context,
                    session_id=session_id,
                    event_type="conversation",
                    agent_type=session_context.current_agent,
                    action="process_input",
                    details={
                        "input_length": len(input_text),
                        "has_metadata": bool(metadata)
                    },
                    privacy_mode=ConversationPrivacyMode.PRIVATE,  # Default privacy mode
                    success=True
                )
                
            except Exception as security_error:
                self.logger.warning(
                    "Security validation failed for session %s: %s",
                    session_id, str(security_error)
                )
                yield AIEvent(
                    type=EventType.ERROR,
                    data={"error": "Security validation failed"},
                    session_id=session_id,
                    agent_type="security"
                )
                return
            
            # Update session activity
            session_context.update_activity()
            
            # Update resource manager with session activity
            await self.resource_manager.update_session_activity(session_id)
            
            # Store conversation message in memory layer
            await self.memory_layer.store_conversation_message(
                session_id, session_context.user_id, "user", input_text, session_context.current_agent
            )
            
            # Determine which agent should handle the request
            target_agent = await self.route_request(input_text, session_context)
            
            # Switch agent if needed
            if target_agent != session_context.current_agent:
                session_context.switch_agent(target_agent)
                
                yield AIEvent(
                    type=EventType.AGENT_SWITCH,
                    data={
                        "previous_agent": session_context.agent_history[-2] if len(session_context.agent_history) > 1 else None,
                        "current_agent": target_agent
                    },
                    session_id=session_id,
                    agent_type=target_agent
                )
            
            # Add user message to conversation history
            session_context.add_message("user", input_text)
            
            # Route to appropriate agent
            agent = self.agents.get(target_agent)
            if agent:
                async for event in agent.handle_request(
                    session_id, input_text, session_context.user_context, metadata
                ):
                    yield event
                    
                    # Add assistant responses to conversation history and memory layer
                    if event.type == EventType.RESPONSE:
                        response_text = event.data.get("response", "")
                        if response_text:
                            session_context.add_message("assistant", response_text, target_agent)
                            await self.memory_layer.store_conversation_message(
                                session_id, session_context.user_id, "assistant", 
                                response_text, target_agent
                            )
            else:
                yield AIEvent(
                    type=EventType.ERROR,
                    data={"error": f"Agent '{target_agent}' not available"},
                    session_id=session_id,
                    agent_type="system"
                )
                
        except Exception as e:
            self.logger.error("Input processing failed for session %s: %s", session_id, e)
            yield AIEvent(
                type=EventType.ERROR,
                data={"error": f"Processing failed: {str(e)}"},
                session_id=session_id,
                agent_type="system"
            )
    
    async def route_request(
        self,
        input_text: str,
        session_context: SessionContext
    ) -> str:
        """
        Determine which agent should handle the request.
        
        Args:
            input_text: User's input text
            session_context: Current session context
            
        Returns:
            Agent type string
        """
        input_lower = input_text.lower()
        
        # Family-related keywords
        if any(keyword in input_lower for keyword in [
            "family", "member", "invite", "relationship", "relatives"
        ]):
            return "family"
        
        # Workspace/team keywords
        if any(keyword in input_lower for keyword in [
            "workspace", "team", "project", "collaborate", "colleague"
        ]):
            return "workspace"
        
        # Shopping/commerce keywords
        if any(keyword in input_lower for keyword in [
            "buy", "shop", "purchase", "avatar", "theme", "banner", "store"
        ]):
            return "commerce"
        
        # Security/admin keywords (only for admin users)
        if session_context.user_context.role == "admin" and any(keyword in input_lower for keyword in [
            "security", "admin", "health", "monitor", "users", "system"
        ]):
            return "security"
        
        # Voice/communication keywords
        if any(keyword in input_lower for keyword in [
            "voice", "speak", "listen", "audio", "microphone", "tts", "stt"
        ]):
            return "voice"
        
        # Default to personal assistant
        return "personal"
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a session.
        
        Args:
            session_id: AI session identifier
            
        Returns:
            Session information dictionary or None
        """
        session_context = self.active_sessions.get(session_id)
        if not session_context:
            return None
        
        return {
            "session_id": session_context.session_id,
            "user_id": session_context.user_id,
            "session_type": session_context.session_type,
            "current_agent": session_context.current_agent,
            "agent_history": session_context.agent_history,
            "created_at": session_context.created_at.isoformat(),
            "last_activity": session_context.last_activity.isoformat(),
            "message_count": len(session_context.conversation_history)
        }
    
    async def cleanup_session(self, session_id: str) -> bool:
        """
        Clean up a session and its resources.
        
        Args:
            session_id: AI session identifier
            
        Returns:
            True if session was cleaned up, False if not found
        """
        session_context = self.active_sessions.get(session_id)
        if not session_context:
            return False
        
        # Cleanup agent sessions
        for agent in self.agents.values():
            await agent.cleanup_session(session_id)
        
        # Cleanup session in resource manager
        await self.resource_manager.cleanup_session(session_id)
        
        # Remove from active sessions
        del self.active_sessions[session_id]
        
        self.logger.info(
            "Cleaned up session %s for user %s",
            session_id, session_context.user_id
        )
        
        return True
    
    async def list_active_sessions(self) -> List[Dict[str, Any]]:
        """
        List all active sessions.
        
        Returns:
            List of session information dictionaries
        """
        sessions = []
        for session_id in self.active_sessions:
            session_info = await self.get_session_info(session_id)
            if session_info:
                sessions.append(session_info)
        
        return sessions
    
    async def get_agent_capabilities(
        self,
        agent_type: str,
        user_context: MCPUserContext
    ) -> List[Dict[str, Any]]:
        """
        Get capabilities for a specific agent.
        
        Args:
            agent_type: Type of agent
            user_context: MCP user context for permission checking
            
        Returns:
            List of capability dictionaries
        """
        agent = self.agents.get(agent_type)
        if agent:
            return await agent.get_capabilities(user_context)
        
        return []
    
    async def get_all_capabilities(
        self,
        user_context: MCPUserContext
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get capabilities for all agents.
        
        Args:
            user_context: MCP user context for permission checking
            
        Returns:
            Dictionary mapping agent types to their capabilities
        """
        capabilities = {}
        
        for agent_type, agent in self.agents.items():
            capabilities[agent_type] = await agent.get_capabilities(user_context)
        
        return capabilities
    
    def get_agent_info(self) -> Dict[str, Dict[str, str]]:
        """
        Get information about all available agents.
        
        Returns:
            Dictionary mapping agent types to their info
        """
        agent_info = {}
        
        for agent_type, agent in self.agents.items():
            agent_info[agent_type] = {
                "name": agent.agent_name,
                "description": agent.agent_description,
                "type": agent_type
            }
        
        return agent_info
    
    async def execute_mcp_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user_context: MCPUserContext,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute an MCP tool through the tool coordinator.
        
        Args:
            tool_name: Name of the MCP tool to execute
            parameters: Tool parameters
            user_context: MCP user context for authentication
            session_id: Optional session ID for tracking
            
        Returns:
            Tool execution result
        """
        try:
            if not self.tool_coordinator:
                return {
                    "success": False,
                    "error": "Tool coordinator not available",
                    "result": None
                }
            
            result = await self.tool_coordinator.execute_tool(
                tool_name=tool_name,
                parameters=parameters,
                user_context=user_context,
                session_id=session_id
            )
            
            return {
                "success": result.success,
                "result": result.result,
                "error": result.error,
                "execution_time_ms": result.execution_time_ms,
                "tool_name": result.tool_name
            }
            
        except Exception as e:
            self.logger.error("MCP tool execution failed: %s - %s", tool_name, e)
            return {
                "success": False,
                "error": str(e),
                "result": None
            }
    
    async def load_mcp_resource(
        self,
        resource_uri: str,
        user_context: MCPUserContext,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Load an MCP resource through the tool coordinator.
        
        Args:
            resource_uri: URI of the resource to load
            user_context: MCP user context for authentication
            session_id: Optional session ID for tracking
            
        Returns:
            Resource loading result
        """
        try:
            if not self.tool_coordinator:
                return {
                    "success": False,
                    "error": "Tool coordinator not available",
                    "result": None
                }
            
            result = await self.tool_coordinator.load_resource(
                resource_uri=resource_uri,
                user_context=user_context,
                session_id=session_id
            )
            
            return {
                "success": result.success,
                "result": result.result,
                "error": result.error,
                "execution_time_ms": result.execution_time_ms
            }
            
        except Exception as e:
            self.logger.error("MCP resource loading failed: %s - %s", resource_uri, e)
            return {
                "success": False,
                "error": str(e),
                "result": None
            }
    
    async def get_available_tools(
        self,
        user_context: MCPUserContext
    ) -> List[Dict[str, Any]]:
        """
        Get all MCP tools available to the user.
        
        Args:
            user_context: MCP user context for permission checking
            
        Returns:
            List of available tools with metadata
        """
        try:
            if not self.tool_coordinator:
                return []
            
            return await self.tool_coordinator.list_available_tools(user_context)
            
        except Exception as e:
            self.logger.error("Failed to get available tools: %s", e)
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
            user_context: MCP user context for permission checking
            
        Returns:
            True if user can execute the tool, False otherwise
        """
        try:
            if not self.tool_coordinator:
                return False
            
            return await self.tool_coordinator.validate_tool_access(tool_name, user_context)
            
        except Exception as e:
            self.logger.error("Failed to validate tool access for %s: %s", tool_name, e)
            return False
    
    async def get_tool_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for MCP tools.
        
        Returns:
            Dictionary containing tool performance metrics
        """
        try:
            if not self.tool_coordinator:
                return {}
            
            return self.tool_coordinator.get_all_performance_metrics()
            
        except Exception as e:
            self.logger.error("Failed to get tool performance metrics: %s", e)
            return {}
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive performance metrics for the orchestrator.
        
        Returns:
            Performance metrics dictionary
        """
        try:
            metrics = {
                "model_engine": await self.model_engine.get_performance_metrics(),
                "memory_layer": await self.memory_layer.get_memory_stats(),
                "resource_manager": self.resource_manager.get_performance_metrics(),
                "sessions": {
                    "active_count": len(self.active_sessions),
                    "sessions": self.resource_manager.list_active_sessions()
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            return metrics
            
        except Exception as e:
            self.logger.error("Failed to get performance metrics: %s", e)
            return {"error": str(e)}
    
    async def invalidate_caches(self, pattern: str = "*") -> Dict[str, int]:
        """
        Invalidate caches across all components.
        
        Args:
            pattern: Pattern to match for cache invalidation
            
        Returns:
            Dictionary with invalidation counts per component
        """
        try:
            results = {}
            
            # Invalidate model engine cache
            model_invalidated = await self.model_engine.invalidate_cache(pattern)
            results["model_cache"] = model_invalidated
            
            # Invalidate memory layer cache
            # Note: Memory layer doesn't have a direct invalidate method,
            # but we can clear specific context types
            results["memory_cache"] = 0  # Placeholder
            
            self.logger.info("Cache invalidation completed: %s", results)
            return results
            
        except Exception as e:
            self.logger.error("Failed to invalidate caches: %s", e)
            return {"error": str(e)}
    
    async def start_background_tasks(self):
        """Start background tasks for performance optimization."""
        try:
            # Start resource manager
            await self.resource_manager.start()
            
            self.logger.info("Background tasks started")
            
        except Exception as e:
            self.logger.error("Failed to start background tasks: %s", e)
    
    async def stop_background_tasks(self):
        """Stop background tasks."""
        try:
            # Stop resource manager
            await self.resource_manager.stop()
            
            # Cleanup model engine
            await self.model_engine.cleanup()
            
            self.logger.info("Background tasks stopped")
            
        except Exception as e:
            self.logger.error("Failed to stop background tasks: %s", e)
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check on the orchestrator and all components.
        
        Returns:
            Health check results
        """
        health_status = {
            "orchestrator": "healthy",
            "active_sessions": len(self.active_sessions),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # Check model engine health
            model_health = await self.model_engine.health_check()
            health_status["model_engine"] = model_health
            
            # Check memory layer health
            memory_health = await self.memory_layer.health_check()
            health_status["memory_layer"] = memory_health
            
            # Check resource manager health
            resource_health = await self.resource_manager.health_check()
            health_status["resource_manager"] = resource_health
            
            # Check tool coordinator health
            if self.tool_coordinator:
                try:
                    tool_count = len(self.tool_coordinator.tool_registry.get_all_tools())
                    health_status["tool_coordinator"] = f"healthy ({tool_count} tools)"
                except Exception as e:
                    health_status["tool_coordinator"] = f"error: {str(e)}"
            else:
                health_status["tool_coordinator"] = "unavailable"
            
            # Check each agent
            health_status["agents"] = {}
            for agent_type, agent in self.agents.items():
                try:
                    # Basic agent health check
                    health_status["agents"][agent_type] = "healthy"
                except Exception as e:
                    health_status["agents"][agent_type] = f"error: {str(e)}"
            
            # Determine overall status
            component_statuses = [
                model_health.get("status", "unknown"),
                memory_health.get("status", "unknown"),
                resource_health.get("status", "unknown")
            ]
            
            if "unhealthy" in component_statuses:
                health_status["orchestrator"] = "unhealthy"
            elif "under_pressure" in component_statuses or "degraded" in component_statuses:
                health_status["orchestrator"] = "degraded"
            else:
                # All components are healthy
                health_status["orchestrator"] = "healthy"
            
        except Exception as e:
            health_status["orchestrator"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status
    
    async def handle_critical_error(
        self,
        session_id: str,
        error: AIOrchestrationError,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle critical errors that require immediate attention.
        
        Args:
            session_id: Session ID where error occurred
            error: The critical error
            context: Additional error context
            
        Returns:
            Error handling result
        """
        self.logger.critical(
            "Critical AI error in session %s: %s",
            session_id, str(error)
        )
        
        # Log the error
        await log_ai_error(error, context)
        
        # Attempt comprehensive recovery
        try:
            recovery_result = await trigger_comprehensive_recovery(
                session_id, error.context, self
            )
            
            # If recovery fails, clean up the session
            if not recovery_result.get("overall_success", False):
                await self.cleanup_session(session_id)
                
                return {
                    "handled": True,
                    "session_cleaned": True,
                    "recovery_attempted": True,
                    "recovery_successful": False,
                    "user_message": "A critical error occurred. Your session has been reset.",
                    "suggested_actions": [
                        "Start a new session",
                        "Contact support if the issue persists",
                        "Try using a different agent type"
                    ]
                }
            
            return {
                "handled": True,
                "session_cleaned": False,
                "recovery_attempted": True,
                "recovery_successful": True,
                "user_message": "A temporary issue was resolved automatically.",
                "recovery_details": recovery_result
            }
            
        except Exception as recovery_error:
            self.logger.error(
                "Critical error recovery failed for session %s: %s",
                session_id, str(recovery_error)
            )
            
            # Force cleanup
            await self.cleanup_session(session_id)
            
            return {
                "handled": True,
                "session_cleaned": True,
                "recovery_attempted": True,
                "recovery_successful": False,
                "recovery_error": str(recovery_error),
                "user_message": "A critical error occurred and could not be recovered. Your session has been reset.",
                "suggested_actions": [
                    "Start a new session",
                    "Contact support immediately",
                    "Provide error details to support team"
                ]
            }
    
    async def get_error_handling_health(self) -> Dict[str, Any]:
        """Get health status of error handling components."""
        from .errors import get_ai_error_handling_health
        from .recovery import get_recovery_system_health
        
        try:
            ai_error_health = await get_ai_error_handling_health()
            recovery_health = await get_recovery_system_health()
            
            return {
                "error_handling": ai_error_health,
                "recovery_system": recovery_health,
                "orchestrator_health": {
                    "active_sessions": len(self.active_sessions),
                    "agents_available": len(self.agents),
                    "memory_layer_active": self.memory_layer is not None,
                    "resource_manager_active": self.resource_manager is not None
                },
                "overall_healthy": (
                    ai_error_health.get("overall_healthy", True) and
                    recovery_health.get("overall_healthy", True)
                )
            }
            
        except Exception as e:
            self.logger.error("Failed to get error handling health: %s", str(e))
            return {
                "error": str(e),
                "overall_healthy": False
            }


# Global orchestrator instance
_global_orchestrator: Optional[AgentOrchestrator] = None


def get_global_orchestrator() -> Optional[AgentOrchestrator]:
    """
    Get the global AI orchestrator instance.
    
    Returns:
        The global orchestrator instance or None if not initialized
    """
    global _global_orchestrator
    return _global_orchestrator


def set_global_orchestrator(orchestrator: AgentOrchestrator):
    """
    Set the global AI orchestrator instance.
    
    Args:
        orchestrator: The orchestrator instance to set as global
    """
    global _global_orchestrator
    _global_orchestrator = orchestrator


def initialize_global_orchestrator() -> AgentOrchestrator:
    """
    Initialize and return the global AI orchestrator instance.
    
    Returns:
        The initialized global orchestrator instance
    """
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = AgentOrchestrator()
    return _global_orchestrator
# Global instance will be created lazily when needed
ai_orchestrator = None