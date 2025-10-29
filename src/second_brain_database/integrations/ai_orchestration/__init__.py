"""
AI Agent Orchestration System

This module provides a comprehensive AI agent orchestration system that integrates
with existing Second Brain Database functionality through FastAPI and MCP tools.

The system implements six specialized AI agents:
- FamilyAssistantAgent: Family management and coordination
- PersonalAssistantAgent: Individual user tasks and preferences
- WorkspaceAgent: Team collaboration and workspace management
- CommerceAgent: Shopping assistance and asset management
- SecurityAgent: Security monitoring and admin operations
- VoiceAgent: Voice interactions and multi-modal communication

All agents leverage existing MCP tools, managers, and database systems for
secure and consistent operation.
"""

from .orchestrator import AgentOrchestrator, SessionContext, ModelEngine
from .models.events import AIEvent, EventType
from .event_bus import AIEventBus, get_ai_event_bus
from .models.session import (
    SessionCreateRequest,
    SessionResponse,
    MessageRequest,
    MessageResponse,
    AgentType,
    SessionStatus
)
from .agents import (
    BaseAgent,
    FamilyAssistantAgent,
    PersonalAssistantAgent,
    WorkspaceAgent,
    CommerceAgent,
    SecurityAgent,
    VoiceAgent,
    AGENT_REGISTRY,
    create_agent,
    get_agent_class,
    get_available_agent_types
)

__all__ = [
    "AgentOrchestrator",
    "SessionContext",
    "ModelEngine",
    "AIEvent",
    "EventType",
    "AIEventBus",
    "get_ai_event_bus",
    "SessionCreateRequest",
    "SessionResponse",
    "MessageRequest",
    "MessageResponse",
    "AgentType",
    "SessionStatus",
    "BaseAgent",
    "FamilyAssistantAgent",
    "PersonalAssistantAgent",
    "WorkspaceAgent",
    "CommerceAgent",
    "SecurityAgent",
    "VoiceAgent",
    "AGENT_REGISTRY",
    "create_agent",
    "get_agent_class",
    "get_available_agent_types"
]

__version__ = "1.0.0"