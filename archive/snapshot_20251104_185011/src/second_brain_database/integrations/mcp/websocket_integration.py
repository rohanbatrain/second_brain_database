"""
Modern MCP WebSocket Integration

This module provides WebSocket integration for MCP that works alongside
the existing AI orchestration WebSocket system. It bridges MCP protocol
messages with the AI event bus for real-time communication.

Key Features:
- MCP protocol WebSocket support
- Integration with existing AI event bus
- Session management and authentication
- Real-time tool execution tracking
- Error handling and recovery
"""

import asyncio
import json
from typing import Dict, Any, Optional, Set
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ...config import settings
from ...managers.logging_manager import get_logger
from ...managers.security_manager import SecurityManager
# AI session manager and metrics removed with ai_orchestration system
# AI orchestration imports removed
from .modern_server import mcp

logger = get_logger(prefix="[MCP_WebSocket]")


class MCPWebSocketSession(BaseModel):
    """MCP WebSocket session information."""
    
    session_id: str
    websocket: WebSocket
    user_id: Optional[str] = None
    authenticated: bool = False
    protocol_version: str = "2024-11-05"
    capabilities: Dict[str, Any] = {}
    created_at: datetime = datetime.now(timezone.utc)
    last_activity: datetime = datetime.now(timezone.utc)
    
    class Config:
        arbitrary_types_allowed = True


class MCPWebSocketManager:
    """
    WebSocket manager for MCP protocol integration.
    
    This manager handles MCP WebSocket connections and integrates them
    with the existing AI orchestration system for unified real-time communication.
    """
    
    def __init__(self, security_manager: SecurityManager):
        # ai_event_bus removed with ai_orchestration system
        self.security_manager = security_manager
        self.active_sessions: Dict[str, MCPWebSocketSession] = {}
        self.websocket_to_session: Dict[WebSocket, str] = {}
        self.ai_sessions: Dict[str, str] = {}  # websocket session -> ai session mapping
        
    async def connect(self, websocket: WebSocket, session_id: str) -> bool:
        """
        Accept and register a new MCP WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            session_id: Unique session identifier
            
        Returns:
            bool: True if connection was successful
        """
        try:
            await websocket.accept()
            
            # Create session
            session = MCPWebSocketSession(
                session_id=session_id,
                websocket=websocket
            )
            
            # Register session
            self.active_sessions[session_id] = session
            self.websocket_to_session[websocket] = session_id
            
            # Register with AI event bus for unified communication
            await self.ai_event_bus.register_session(session_id, websocket)
            
            logger.info("MCP WebSocket connected: session=%s", session_id)
            
            # Send initial capabilities
            await self._send_capabilities(session)
            
            return True
            
        except Exception as e:
            logger.error("Failed to connect MCP WebSocket: %s", e)
            return False
    
    async def disconnect(self, websocket: WebSocket):
        """
        Disconnect and cleanup MCP WebSocket session.
        
        Args:
            websocket: The WebSocket connection to disconnect
        """
        session_id = self.websocket_to_session.get(websocket)
        if not session_id:
            return
        
        try:
            # End AI session if connected
            ai_session_id = self.ai_sessions.get(session_id)
            if ai_session_id:
                try:
                    await ai_session_manager.end_session(ai_session_id)
                except Exception as e:
                    logger.warning("Failed to end AI session %s: %s", ai_session_id, e)
            
            # Unregister from AI event bus
            await self.ai_event_bus.unregister_session(session_id)
            
            # Cleanup session mappings
            self.active_sessions.pop(session_id, None)
            self.websocket_to_session.pop(websocket, None)
            self.ai_sessions.pop(session_id, None)
            
            logger.info("MCP WebSocket disconnected: session=%s", session_id)
            
        except Exception as e:
            logger.error("Error disconnecting MCP WebSocket: %s", e)
    
    async def handle_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """
        Handle incoming MCP protocol message.
        
        Args:
            websocket: The WebSocket connection
            message: The MCP protocol message
        """
        session_id = self.websocket_to_session.get(websocket)
        if not session_id:
            logger.error("Received message from unregistered WebSocket")
            return
        
        session = self.active_sessions.get(session_id)
        if not session:
            logger.error("Session not found: %s", session_id)
            return
        
        # Update last activity
        session.last_activity = datetime.now(timezone.utc)
        
        try:
            method = message.get("method", "unknown")
            message_id = message.get("id")
            
            logger.info("MCP WebSocket message: session=%s, method=%s", session_id, method)
            
            # Route MCP protocol messages
            if method == "initialize":
                await self._handle_initialize(session, message)
            elif method == "tools/list":
                await self._handle_tools_list(session, message)
            elif method == "tools/call":
                await self._handle_tool_call(session, message)
            elif method == "resources/list":
                await self._handle_resources_list(session, message)
            elif method == "resources/read":
                await self._handle_resource_read(session, message)
            elif method == "prompts/list":
                await self._handle_prompts_list(session, message)
            elif method == "prompts/get":
                await self._handle_prompt_get(session, message)
            # AI-specific message types
            elif method == "ai/create_session":
                await self._handle_ai_create_session(session, message)
            elif method == "ai/send_message":
                await self._handle_ai_send_message(session, message)
            elif method == "ai/switch_agent":
                await self._handle_ai_switch_agent(session, message)
            elif method == "ai/voice_input":
                await self._handle_ai_voice_input(session, message)
            elif method == "ai/token_stream":
                await self._handle_ai_token_stream(session, message)
            else:
                # Unknown method
                await self._send_error(session, message_id, -32601, f"Method not found: {method}")
            
        except Exception as e:
            logger.error("Error handling MCP message: %s", e)
            await self._send_error(session, message.get("id"), -32603, str(e))
    
    async def _send_capabilities(self, session: MCPWebSocketSession):
        """Send server capabilities to client."""
        capabilities = {
            "jsonrpc": "2.0",
            "id": None,
            "result": {
                "protocolVersion": session.protocol_version,
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {},
                    "logging": {}
                },
                "serverInfo": {
                    "name": mcp.name,
                    "version": mcp.version
                }
            }
        }
        
        await session.websocket.send_json(capabilities)
    
    async def _handle_initialize(self, session: MCPWebSocketSession, message: Dict[str, Any]):
        """Handle MCP initialize request."""
        params = message.get("params", {})
        client_info = params.get("clientInfo", {})
        
        logger.info("MCP client initializing: %s", client_info.get("name", "unknown"))
        
        # Update session capabilities
        session.capabilities = params.get("capabilities", {})
        
        # Send initialization response
        response = {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "protocolVersion": session.protocol_version,
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {},
                    "logging": {}
                },
                "serverInfo": {
                    "name": mcp.name,
                    "version": mcp.version
                }
            }
        }
        
        await session.websocket.send_json(response)
        
        # AI event bus removed - session start event no longer emitted
    
    async def _handle_tools_list(self, session: MCPWebSocketSession, message: Dict[str, Any]):
        """Handle tools/list request."""
        # In FastMCP 2.x, tools are registered via decorators
        # We'll return a basic list for now - in production this would be dynamic
        tools = [
            {
                "name": "get_family_info",
                "description": "Get family information and details",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "family_id": {"type": "string", "description": "Family ID"}
                    }
                }
            },
            {
                "name": "create_family",
                "description": "Create a new family",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Family name"},
                        "description": {"type": "string", "description": "Family description"}
                    },
                    "required": ["name"]
                }
            }
        ]
        
        response = {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "tools": tools
            }
        }
        
        await session.websocket.send_json(response)
    
    async def _handle_tool_call(self, session: MCPWebSocketSession, message: Dict[str, Any]):
        """Handle tools/call request."""
        params = message.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        # Emit tool call event to AI event bus
        await self.ai_event_bus.emit_tool_call(
            session.session_id,
            tool_name,
            arguments
        )
        
        try:
            # In a real implementation, this would call the actual FastMCP tool
            # For now, we'll simulate a successful response
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": f"Tool {tool_name} executed successfully via WebSocket"
                    }
                ]
            }
            
            response = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": result
            }
            
            await session.websocket.send_json(response)
            
            # Emit tool result event
            await self.ai_event_bus.emit_tool_result(
                session.session_id,
                tool_name,
                result,
                success=True
            )
            
        except Exception as e:
            logger.error("Tool execution failed: %s", e)
            await self._send_error(session, message.get("id"), -32603, f"Tool execution failed: {str(e)}")
            
            # Emit tool error event
            await self.ai_event_bus.emit_tool_result(
                session.session_id,
                tool_name,
                {"error": str(e)},
                success=False
            )
    
    async def _handle_resources_list(self, session: MCPWebSocketSession, message: Dict[str, Any]):
        """Handle resources/list request."""
        resources = []  # Would be populated from FastMCP resource registry
        
        response = {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "resources": resources
            }
        }
        
        await session.websocket.send_json(response)
    
    async def _handle_resource_read(self, session: MCPWebSocketSession, message: Dict[str, Any]):
        """Handle resources/read request."""
        params = message.get("params", {})
        uri = params.get("uri")
        
        # Placeholder implementation
        response = {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "text/plain",
                        "text": f"Resource content for {uri}"
                    }
                ]
            }
        }
        
        await session.websocket.send_json(response)
    
    async def _handle_prompts_list(self, session: MCPWebSocketSession, message: Dict[str, Any]):
        """Handle prompts/list request."""
        prompts = []  # Would be populated from FastMCP prompt registry
        
        response = {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "prompts": prompts
            }
        }
        
        await session.websocket.send_json(response)
    
    async def _handle_prompt_get(self, session: MCPWebSocketSession, message: Dict[str, Any]):
        """Handle prompts/get request."""
        params = message.get("params", {})
        name = params.get("name")
        
        # Placeholder implementation
        response = {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "description": f"Prompt {name}",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"This is prompt {name}"
                        }
                    }
                ]
            }
        }
        
        await session.websocket.send_json(response)
    
    async def _handle_ai_create_session(self, session: MCPWebSocketSession, message: Dict[str, Any]):
        """Handle AI session creation request."""
        params = message.get("params", {})
        agent_type = params.get("agent_type", "personal")
        session_name = params.get("session_name")
        voice_enabled = params.get("voice_enabled", False)
        context = params.get("context", {})
        
        try:
            # Create AI session using the AI session manager
            ai_session = await ai_session_manager.create_session(
                user_id=session.user_id or "anonymous",
                agent_type=AgentType(agent_type),
                session_name=session_name,
                voice_enabled=voice_enabled,
                context=context
            )
            
            # Map WebSocket session to AI session
            self.ai_sessions[session.session_id] = ai_session["session_id"]
            
            response = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "ai_session_id": ai_session["session_id"],
                    "agent_type": ai_session["agent_type"],
                    "session_name": ai_session["session_name"],
                    "voice_enabled": ai_session["voice_enabled"],
                    "created_at": ai_session["created_at"].isoformat(),
                    "expires_at": ai_session["expires_at"].isoformat()
                }
            }
            
            await session.websocket.send_json(response)
            
        except Exception as e:
            logger.error("Failed to create AI session: %s", e)
            await self._send_error(session, message.get("id"), -32603, f"Failed to create AI session: {str(e)}")
    
    async def _handle_ai_send_message(self, session: MCPWebSocketSession, message: Dict[str, Any]):
        """Handle AI message sending."""
        params = message.get("params", {})
        content = params.get("content", "")
        message_type = params.get("message_type", "text")
        metadata = params.get("metadata", {})
        
        try:
            ai_session_id = self.ai_sessions.get(session.session_id)
            if not ai_session_id:
                await self._send_error(session, message.get("id"), -32602, "No AI session active")
                return
            
            # Send message to AI session
            message_doc = await ai_session_manager.send_message(
                session_id=ai_session_id,
                content=content,
                message_type=MessageType(message_type),
                role=MessageRole.USER,
                metadata=metadata,
                user_id=session.user_id
            )
            
            response = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "message_id": message_doc["message_id"],
                    "timestamp": message_doc["timestamp"].isoformat(),
                    "status": "sent"
                }
            }
            
            await session.websocket.send_json(response)
            
            # Simulate AI response (in real implementation, this would trigger agent processing)
            await self._simulate_ai_response(session, ai_session_id, content)
            
        except Exception as e:
            logger.error("Failed to send AI message: %s", e)
            await self._send_error(session, message.get("id"), -32603, f"Failed to send message: {str(e)}")
    
    async def _handle_ai_switch_agent(self, session: MCPWebSocketSession, message: Dict[str, Any]):
        """Handle agent switching request."""
        params = message.get("params", {})
        new_agent_type = params.get("agent_type")
        
        try:
            ai_session_id = self.ai_sessions.get(session.session_id)
            if not ai_session_id:
                await self._send_error(session, message.get("id"), -32602, "No AI session active")
                return
            
            # In a real implementation, this would update the AI session's agent type
            # For now, we'll just acknowledge the switch
            response = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "agent_type": new_agent_type,
                    "switched_at": datetime.now(timezone.utc).isoformat(),
                    "status": "switched"
                }
            }
            
            await session.websocket.send_json(response)
            
            # Notify about agent switch
            await self._send_ai_event(session, {
                "type": "agent_switched",
                "agent_type": new_agent_type,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error("Failed to switch agent: %s", e)
            await self._send_error(session, message.get("id"), -32603, f"Failed to switch agent: {str(e)}")
    
    async def _handle_ai_voice_input(self, session: MCPWebSocketSession, message: Dict[str, Any]):
        """Handle voice input processing."""
        params = message.get("params", {})
        audio_data = params.get("audio_data")
        audio_format = params.get("format", "wav")
        
        try:
            ai_session_id = self.ai_sessions.get(session.session_id)
            if not ai_session_id:
                await self._send_error(session, message.get("id"), -32602, "No AI session active")
                return
            
            # In a real implementation, this would process the audio data
            # For now, we'll simulate voice processing
            response = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "transcription": "Voice input processed",
                    "confidence": 0.95,
                    "processing_time_ms": 150,
                    "status": "processed"
                }
            }
            
            await session.websocket.send_json(response)
            
        except Exception as e:
            logger.error("Failed to process voice input: %s", e)
            await self._send_error(session, message.get("id"), -32603, f"Failed to process voice input: {str(e)}")
    
    async def _handle_ai_token_stream(self, session: MCPWebSocketSession, message: Dict[str, Any]):
        """Handle token streaming request."""
        params = message.get("params", {})
        enable_streaming = params.get("enable", True)
        
        try:
            response = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "streaming_enabled": enable_streaming,
                    "status": "configured"
                }
            }
            
            await session.websocket.send_json(response)
            
        except Exception as e:
            logger.error("Failed to configure token streaming: %s", e)
            await self._send_error(session, message.get("id"), -32603, f"Failed to configure streaming: {str(e)}")
    
    async def _simulate_ai_response(self, session: MCPWebSocketSession, ai_session_id: str, user_message: str):
        """Simulate AI response for demonstration purposes."""
        try:
            # Simulate thinking
            await self._send_ai_event(session, {
                "type": "thinking",
                "message": "Processing your request...",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            # Simulate token streaming
            response_tokens = ["I", " understand", " your", " request.", " Let", " me", " help", " you", " with", " that."]
            for token in response_tokens:
                await self._send_ai_event(session, {
                    "type": "token",
                    "token": token,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                await asyncio.sleep(0.1)  # Simulate streaming delay
            
            # Send complete response
            await self._send_ai_event(session, {
                "type": "response_complete",
                "message": "I understand your request. Let me help you with that.",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error("Failed to simulate AI response: %s", e)
    
    async def _send_ai_event(self, session: MCPWebSocketSession, event_data: Dict[str, Any]):
        """Send AI event to client."""
        try:
            ai_event = {
                "jsonrpc": "2.0",
                "method": "ai/event",
                "params": event_data
            }
            await session.websocket.send_json(ai_event)
        except Exception as e:
            logger.error("Failed to send AI event: %s", e)
    
    async def _send_error(self, session: MCPWebSocketSession, message_id: Optional[str], code: int, message: str):
        """Send error response to client."""
        error_response = {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": {
                "code": code,
                "message": message
            }
        }
        
        await session.websocket.send_json(error_response)
    
    async def broadcast_to_mcp_sessions(self, event_data: Dict[str, Any]):
        """
        Broadcast event to all active MCP WebSocket sessions.
        
        Args:
            event_data: Event data to broadcast
        """
        if not self.active_sessions:
            return
        
        disconnected_sessions = []
        
        for session_id, session in self.active_sessions.items():
            try:
                await session.websocket.send_json(event_data)
            except Exception as e:
                logger.error("Failed to send to MCP session %s: %s", session_id, e)
                disconnected_sessions.append(session.websocket)
        
        # Cleanup disconnected sessions
        for websocket in disconnected_sessions:
            await self.disconnect(websocket)
    
    def get_active_session_count(self) -> int:
        """Get count of active MCP WebSocket sessions."""
        return len(self.active_sessions)
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific session."""
        session = self.active_sessions.get(session_id)
        if not session:
            return None
        
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "authenticated": session.authenticated,
            "protocol_version": session.protocol_version,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "capabilities": session.capabilities
        }


# Global MCP WebSocket manager instance
mcp_websocket_manager: Optional[MCPWebSocketManager] = None


def get_mcp_websocket_manager() -> Optional[MCPWebSocketManager]:
    """Get the global MCP WebSocket manager instance."""
    return mcp_websocket_manager


async def initialize_mcp_websocket_manager(security_manager: SecurityManager):
    """Initialize the global MCP WebSocket manager."""
    global mcp_websocket_manager
    
    if mcp_websocket_manager is None:
        mcp_websocket_manager = MCPWebSocketManager(security_manager)
        logger.info("MCP WebSocket manager initialized (AI orchestration removed)")
    
    return mcp_websocket_manager