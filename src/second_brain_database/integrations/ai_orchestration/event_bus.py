"""
AI Event Bus

This module provides real-time event streaming for AI agent interactions,
extending the existing WebSocket manager to handle AI-specific events.
"""

import json
import asyncio
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timezone
import logging

from fastapi import WebSocket

from second_brain_database.websocket_manager import ConnectionManager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.integrations.ai_orchestration.models.events import AIEvent, EventType

logger = get_logger(prefix="[AI_EventBus]")


class AIEventBus:
    """
    AI Event Bus for real-time communication with frontend clients.
    
    Extends the existing ConnectionManager to provide AI-specific event streaming
    capabilities including token streaming, tool execution updates, and multi-modal
    coordination between text and voice channels.
    """
    
    def __init__(self, websocket_manager: ConnectionManager):
        self.websocket_manager = websocket_manager
        self.ai_sessions: Dict[str, Set[str]] = {}  # session_id -> set of user_ids
        self.session_websockets: Dict[str, List[WebSocket]] = {}  # session_id -> websockets
        self.user_sessions: Dict[str, Set[str]] = {}  # user_id -> set of session_ids
        self.event_handlers: Dict[str, List[callable]] = {}
        self.event_buffer: Dict[str, List[AIEvent]] = {}  # session_id -> buffered events
        self.buffer_lock = asyncio.Lock()
        
        logger.info("AI Event Bus initialized")
    
    async def register_session(self, session_id: str, user_id: str, websocket: WebSocket) -> None:
        """
        Register a WebSocket connection for an AI session.
        
        Args:
            session_id: AI session identifier
            user_id: User identifier
            websocket: WebSocket connection
        """
        try:
            # Add to session tracking
            if session_id not in self.ai_sessions:
                self.ai_sessions[session_id] = set()
                self.session_websockets[session_id] = []
                self.event_buffer[session_id] = []
            
            self.ai_sessions[session_id].add(user_id)
            self.session_websockets[session_id].append(websocket)
            
            # Add to user tracking
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = set()
            self.user_sessions[user_id].add(session_id)
            
            logger.info(f"Registered AI session {session_id} for user {user_id}")
            
            # Send any buffered events
            await self._send_buffered_events(session_id, websocket)
            
        except Exception as e:
            logger.error(f"Error registering AI session {session_id}: {e}")
            raise
    
    async def unregister_session(self, session_id: str, user_id: str, websocket: WebSocket) -> None:
        """
        Unregister a WebSocket connection from an AI session.
        
        Args:
            session_id: AI session identifier
            user_id: User identifier
            websocket: WebSocket connection
        """
        try:
            # Remove from session tracking
            if session_id in self.ai_sessions:
                self.ai_sessions[session_id].discard(user_id)
                if websocket in self.session_websockets.get(session_id, []):
                    self.session_websockets[session_id].remove(websocket)
                
                # Clean up empty sessions
                if not self.ai_sessions[session_id]:
                    del self.ai_sessions[session_id]
                    del self.session_websockets[session_id]
                    # Clear event buffer for closed session
                    if session_id in self.event_buffer:
                        del self.event_buffer[session_id]
            
            # Remove from user tracking
            if user_id in self.user_sessions:
                self.user_sessions[user_id].discard(session_id)
                if not self.user_sessions[user_id]:
                    del self.user_sessions[user_id]
            
            logger.info(f"Unregistered AI session {session_id} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error unregistering AI session {session_id}: {e}")
    
    async def emit_event(self, event: AIEvent) -> None:
        """
        Emit an AI event to all connected clients for the session.
        
        Args:
            event: AI event to emit
        """
        try:
            session_id = event.session_id
            
            # Get WebSocket connections for this session
            websockets = self.session_websockets.get(session_id, [])
            
            if not websockets:
                # Buffer the event if no active connections
                async with self.buffer_lock:
                    if session_id not in self.event_buffer:
                        self.event_buffer[session_id] = []
                    self.event_buffer[session_id].append(event)
                    
                    # Limit buffer size to prevent memory issues
                    if len(self.event_buffer[session_id]) > 100:
                        self.event_buffer[session_id] = self.event_buffer[session_id][-50:]
                
                logger.debug(f"Buffered event {event.type} for session {session_id} (no active connections)")
                return
            
            # Convert event to WebSocket message
            message = json.dumps(event.to_websocket_message())
            
            # Send to all WebSocket connections for this session
            disconnected_websockets = []
            for websocket in websockets:
                try:
                    await websocket.send_text(message)
                except Exception as e:
                    logger.warning(f"Failed to send event to WebSocket: {e}")
                    disconnected_websockets.append(websocket)
            
            # Clean up disconnected WebSockets
            for websocket in disconnected_websockets:
                if websocket in self.session_websockets[session_id]:
                    self.session_websockets[session_id].remove(websocket)
            
            logger.debug(f"Emitted {event.type} event to {len(websockets) - len(disconnected_websockets)} connections for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error emitting AI event: {e}")
            raise
    
    async def emit_token_stream(self, session_id: str, agent_type: str, token: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit a streaming token event for real-time AI response generation.
        
        Args:
            session_id: AI session identifier
            agent_type: Type of AI agent generating the token
            token: Token string to stream
            metadata: Optional metadata for the token
        """
        event = AIEvent.create_token_event(session_id, agent_type, token, metadata)
        await self.emit_event(event)
    
    async def emit_tool_call(self, session_id: str, agent_type: str, tool_name: str, parameters: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit a tool call event when an AI agent executes an MCP tool.
        
        Args:
            session_id: AI session identifier
            agent_type: Type of AI agent making the tool call
            tool_name: Name of the MCP tool being called
            parameters: Tool parameters
            metadata: Optional metadata for the tool call
        """
        event = AIEvent.create_tool_call_event(session_id, agent_type, tool_name, parameters, metadata)
        await self.emit_event(event)
    
    async def emit_tool_result(self, session_id: str, agent_type: str, tool_name: str, result: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit a tool result event when an MCP tool execution completes.
        
        Args:
            session_id: AI session identifier
            agent_type: Type of AI agent that executed the tool
            tool_name: Name of the MCP tool that was executed
            result: Tool execution result
            metadata: Optional metadata for the tool result
        """
        event = AIEvent.create_tool_result_event(session_id, agent_type, tool_name, result, metadata)
        await self.emit_event(event)
    
    async def emit_status_update(self, session_id: str, agent_type: str, status: EventType, message: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit a status update event (thinking, typing, waiting, etc.).
        
        Args:
            session_id: AI session identifier
            agent_type: Type of AI agent
            status: Status event type
            message: Optional status message
            metadata: Optional metadata for the status
        """
        event = AIEvent.create_status_event(session_id, agent_type, status, message, metadata)
        await self.emit_event(event)
    
    async def emit_error(self, session_id: str, agent_type: str, error_message: str, error_code: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit an error event when something goes wrong during AI processing.
        
        Args:
            session_id: AI session identifier
            agent_type: Type of AI agent that encountered the error
            error_message: Error message
            error_code: Optional error code
            metadata: Optional metadata for the error
        """
        event = AIEvent.create_error_event(session_id, agent_type, error_message, error_code, metadata)
        await self.emit_event(event)
    
    async def emit_tts_audio(self, session_id: str, agent_type: str, audio_data: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit a TTS audio event for voice responses.
        
        Args:
            session_id: AI session identifier
            agent_type: Type of AI agent generating the audio
            audio_data: Base64-encoded audio data
            metadata: Optional metadata for the audio
        """
        event = AIEvent.create_tts_event(session_id, agent_type, audio_data, metadata)
        await self.emit_event(event)
    
    async def emit_voice_start(self, session_id: str, agent_type: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit a voice processing start event.
        
        Args:
            session_id: AI session identifier
            agent_type: Type of AI agent starting voice processing
            metadata: Optional metadata for the voice processing
        """
        event = AIEvent.create_status_event(session_id, agent_type, EventType.VOICE_START, "Voice processing started", metadata)
        await self.emit_event(event)
    
    async def emit_stt_result(self, session_id: str, agent_type: str, transcribed_text: str, confidence: float = 0.9, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit a speech-to-text result event.
        
        Args:
            session_id: AI session identifier
            agent_type: Type of AI agent that performed STT
            transcribed_text: The transcribed text
            confidence: Confidence score for the transcription
            metadata: Optional metadata for the STT result
        """
        stt_data = {
            "transcribed_text": transcribed_text,
            "confidence": confidence
        }
        if metadata:
            stt_data.update(metadata)
        
        event = AIEvent(
            type=EventType.STT,
            data=stt_data,
            session_id=session_id,
            agent_type=agent_type,
            timestamp=datetime.now(timezone.utc)
        )
        await self.emit_event(event)
    
    async def emit_livekit_event(self, session_id: str, agent_type: str, event_type: str, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit a LiveKit-specific event for voice communication.
        
        Args:
            session_id: AI session identifier
            agent_type: Type of AI agent
            event_type: LiveKit event type (room_joined, track_published, etc.)
            data: Event data
            metadata: Optional metadata
        """
        livekit_data = {
            "event_type": event_type,
            **data
        }
        if metadata:
            livekit_data.update(metadata)
        
        event = AIEvent(
            type=EventType.VOICE_START,  # Using VOICE_START as a generic voice event type
            data=livekit_data,
            session_id=session_id,
            agent_type=agent_type,
            timestamp=datetime.now(timezone.utc)
        )
        await self.emit_event(event)
    
    async def broadcast_to_family(self, family_id: str, event: AIEvent) -> None:
        """
        Broadcast an AI event to all family members.
        
        Args:
            family_id: Family identifier
            event: AI event to broadcast
        """
        try:
            # This would require integration with family management
            # For now, we'll log the intent and implement later
            logger.info(f"Broadcasting AI event {event.type} to family {family_id}")
            
            # TODO: Implement family member lookup and broadcast
            # This would involve:
            # 1. Get all family members from FamilyManager
            # 2. Find active sessions for each member
            # 3. Emit event to each active session
            
        except Exception as e:
            logger.error(f"Error broadcasting to family {family_id}: {e}")
    
    async def subscribe_to_events(self, session_id: str, event_types: List[EventType], handler: callable) -> None:
        """
        Subscribe to specific event types for a session.
        
        Args:
            session_id: AI session identifier
            event_types: List of event types to subscribe to
            handler: Event handler function
        """
        for event_type in event_types:
            key = f"{session_id}:{event_type.value}"
            if key not in self.event_handlers:
                self.event_handlers[key] = []
            self.event_handlers[key].append(handler)
        
        logger.debug(f"Subscribed to {len(event_types)} event types for session {session_id}")
    
    async def unsubscribe_from_events(self, session_id: str, event_types: List[EventType], handler: callable) -> None:
        """
        Unsubscribe from specific event types for a session.
        
        Args:
            session_id: AI session identifier
            event_types: List of event types to unsubscribe from
            handler: Event handler function to remove
        """
        for event_type in event_types:
            key = f"{session_id}:{event_type.value}"
            if key in self.event_handlers and handler in self.event_handlers[key]:
                self.event_handlers[key].remove(handler)
                if not self.event_handlers[key]:
                    del self.event_handlers[key]
        
        logger.debug(f"Unsubscribed from {len(event_types)} event types for session {session_id}")
    
    async def _send_buffered_events(self, session_id: str, websocket: WebSocket) -> None:
        """
        Send any buffered events to a newly connected WebSocket.
        
        Args:
            session_id: AI session identifier
            websocket: WebSocket connection
        """
        try:
            async with self.buffer_lock:
                buffered_events = self.event_buffer.get(session_id, [])
                
                if buffered_events:
                    logger.info(f"Sending {len(buffered_events)} buffered events to session {session_id}")
                    
                    for event in buffered_events:
                        try:
                            message = json.dumps(event.to_websocket_message())
                            await websocket.send_text(message)
                        except Exception as e:
                            logger.warning(f"Failed to send buffered event: {e}")
                            break
                    
                    # Clear buffer after sending
                    self.event_buffer[session_id] = []
                    
        except Exception as e:
            logger.error(f"Error sending buffered events: {e}")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get statistics about active AI sessions and connections.
        
        Returns:
            Dictionary containing session statistics
        """
        return {
            "active_sessions": len(self.ai_sessions),
            "total_connections": sum(len(websockets) for websockets in self.session_websockets.values()),
            "active_users": len(self.user_sessions),
            "buffered_events": sum(len(events) for events in self.event_buffer.values()),
            "event_handlers": len(self.event_handlers)
        }


# Global AI event bus instance
ai_event_bus: Optional[AIEventBus] = None


def get_ai_event_bus() -> AIEventBus:
    """
    Get the global AI event bus instance.
    
    Returns:
        AIEventBus instance
    """
    global ai_event_bus
    if ai_event_bus is None:
        from second_brain_database.websocket_manager import manager
        ai_event_bus = AIEventBus(manager)
    return ai_event_bus