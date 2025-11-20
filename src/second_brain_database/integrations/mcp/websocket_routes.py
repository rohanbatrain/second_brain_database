"""
MCP WebSocket Routes

This module provides WebSocket routes for MCP protocol integration
that work alongside the existing AI orchestration system.
"""

import asyncio
import json
from typing import Any, Dict, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer

from ...config import settings
from ...managers.logging_manager import get_logger
from ...managers.security_manager import SecurityManager

# AIEventBus removed with ai_orchestration system
from .websocket_integration import MCPWebSocketManager, initialize_mcp_websocket_manager

logger = get_logger(prefix="[MCP_WebSocket_Routes]")

# Create router for MCP WebSocket endpoints
router = APIRouter(prefix="/mcp", tags=["MCP WebSocket"])

# Security
security = HTTPBearer(auto_error=False)

# Global managers (will be initialized on startup)
mcp_websocket_manager: Optional[MCPWebSocketManager] = None
security_manager: Optional[SecurityManager] = None


async def get_mcp_websocket_manager() -> MCPWebSocketManager:
    """Get the MCP WebSocket manager instance."""
    global mcp_websocket_manager
    if mcp_websocket_manager is None:
        raise HTTPException(status_code=503, detail="MCP WebSocket manager not initialized")
    return mcp_websocket_manager


async def initialize_managers():
    """Initialize the MCP WebSocket manager and dependencies."""
    global mcp_websocket_manager, security_manager

    try:
        # Initialize security manager
        security_manager = SecurityManager()

        # Initialize MCP WebSocket manager
        mcp_websocket_manager = await initialize_mcp_websocket_manager(security_manager)

        logger.info("MCP WebSocket managers initialized successfully")

    except Exception as e:
        logger.error("Failed to initialize MCP WebSocket managers: %s", e)
        raise


@router.websocket("/ws")
async def mcp_websocket_endpoint(websocket: WebSocket):
    """
    Main MCP WebSocket endpoint for real-time MCP protocol communication.

    This endpoint provides:
    - MCP protocol message handling
    - Session management and authentication
    - Real-time tool execution tracking
    """
    session_id = str(uuid.uuid4())
    manager = await get_mcp_websocket_manager()

    # Accept connection
    connected = await manager.connect(websocket, session_id)
    if not connected:
        await websocket.close(code=1011, reason="Failed to establish MCP session")
        return

    try:
        logger.info("MCP WebSocket session started: %s", session_id)

        while True:
            # Receive message from client
            try:
                data = await websocket.receive_json()
            except Exception as e:
                logger.error("Error receiving WebSocket message: %s", e)
                break

            # Handle MCP protocol message
            await manager.handle_message(websocket, data)

    except WebSocketDisconnect:
        logger.info("MCP WebSocket client disconnected: %s", session_id)
    except Exception as e:
        logger.error("MCP WebSocket error for session %s: %s", session_id, e)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:  # TODO: Use specific exception type
            pass
    finally:
        # Cleanup session
        await manager.disconnect(websocket)


@router.websocket("/ws/{session_id}")
async def mcp_websocket_with_session(websocket: WebSocket, session_id: str):
    """
    MCP WebSocket endpoint with explicit session ID.

    This allows clients to reconnect to existing sessions or
    coordinate multiple connections with the same session.
    """
    manager = await get_mcp_websocket_manager()

    # Accept connection with provided session ID
    connected = await manager.connect(websocket, session_id)
    if not connected:
        await websocket.close(code=1011, reason="Failed to establish MCP session")
        return

    try:
        logger.info("MCP WebSocket session resumed/started: %s", session_id)

        while True:
            # Receive message from client
            try:
                data = await websocket.receive_json()
            except Exception as e:
                logger.error("Error receiving WebSocket message: %s", e)
                break

            # Handle MCP protocol message
            await manager.handle_message(websocket, data)

    except WebSocketDisconnect:
        logger.info("MCP WebSocket client disconnected: %s", session_id)
    except Exception as e:
        logger.error("MCP WebSocket error for session %s: %s", session_id, e)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:  # TODO: Use specific exception type
            pass
    finally:
        # Cleanup session
        await manager.disconnect(websocket)


@router.get("/ws/sessions")
async def list_mcp_websocket_sessions():
    """List active MCP WebSocket sessions."""
    manager = await get_mcp_websocket_manager()

    sessions = []
    for session_id in manager.active_sessions:
        session_info = manager.get_session_info(session_id)
        if session_info:
            sessions.append(session_info)

    return {"active_sessions": len(sessions), "sessions": sessions}


@router.get("/ws/sessions/{session_id}")
async def get_mcp_websocket_session(session_id: str):
    """Get information about a specific MCP WebSocket session."""
    manager = await get_mcp_websocket_manager()

    session_info = manager.get_session_info(session_id)
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    return session_info


@router.post("/ws/broadcast")
async def broadcast_to_mcp_sessions(message: Dict[str, Any]):
    """
    Broadcast a message to all active MCP WebSocket sessions.

    This is useful for system-wide notifications or updates.
    """
    manager = await get_mcp_websocket_manager()

    await manager.broadcast_to_mcp_sessions(message)

    return {"message": "Broadcast sent", "active_sessions": manager.get_active_session_count()}


@router.get("/ws/health")
async def mcp_websocket_health():
    """Health check for MCP WebSocket functionality."""
    try:
        manager = await get_mcp_websocket_manager()

        return {
            "status": "healthy",
            "active_sessions": manager.get_active_session_count(),
            "websocket_enabled": True,
            "mcp_protocol": "2024-11-05",
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "websocket_enabled": False}


# Startup event to initialize managers
@router.on_event("startup")
async def startup_event():
    """Initialize MCP WebSocket managers on startup."""
    await initialize_managers()


# Include additional WebSocket-related endpoints
@router.get("/protocol/info")
async def mcp_protocol_info():
    """Get MCP protocol information and capabilities."""
    return {
        "protocol_version": "2024-11-05",
        "server_name": settings.MCP_SERVER_NAME,
        "server_version": settings.MCP_SERVER_VERSION,
        "transports": ["http", "websocket"],
        "capabilities": {"tools": True, "resources": True, "prompts": True, "logging": True},
        "authentication": {
            "enabled": settings.MCP_SECURITY_ENABLED,
            "required": settings.MCP_REQUIRE_AUTH,
            "methods": ["bearer_token"] if settings.MCP_SECURITY_ENABLED else [],
        },
        "websocket": {
            "enabled": True,
            "endpoints": ["/mcp/ws", "/mcp/ws/{session_id}"],
            "features": ["real_time_tools", "session_management", "event_broadcasting"],
        },
    }


@router.get("/integration/status")
async def mcp_integration_status():
    """Get status of MCP integration."""
    try:
        manager = await get_mcp_websocket_manager()

        return {
            "status": "integrated",
            "mcp_websocket_manager": "initialized",
            "security_manager": "initialized" if security_manager else "not_initialized",
            "active_mcp_sessions": manager.get_active_session_count(),
            "features": {
                "real_time_communication": True,
                "tool_execution_tracking": True,
                "session_management": True,
                "event_broadcasting": True,
            },
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "features": {
                "real_time_communication": False,
                "tool_execution_tracking": False,
                "session_management": False,
                "event_broadcasting": False,
            },
        }
