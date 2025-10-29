"""
AI Agents Module

This module contains all specialized AI agents for the orchestration system.
Each agent handles specific domains and integrates with existing MCP tools
and managers for secure and consistent operation.
"""

from .base_agent import BaseAgent
from .family_agent import FamilyAssistantAgent
from .personal_agent import PersonalAssistantAgent
from .workspace_agent import WorkspaceAgent
from .commerce_agent import CommerceAgent
from .security_agent import SecurityAgent
from .voice_agent import VoiceAgent

__all__ = [
    "BaseAgent",
    "FamilyAssistantAgent",
    "PersonalAssistantAgent", 
    "WorkspaceAgent",
    "CommerceAgent",
    "SecurityAgent",
    "VoiceAgent"
]

# Agent registry for easy access
AGENT_REGISTRY = {
    "family": FamilyAssistantAgent,
    "personal": PersonalAssistantAgent,
    "workspace": WorkspaceAgent,
    "commerce": CommerceAgent,
    "security": SecurityAgent,
    "voice": VoiceAgent
}

def get_agent_class(agent_type: str) -> type:
    """
    Get agent class by type.
    
    Args:
        agent_type: Type of agent to get
        
    Returns:
        Agent class or None if not found
    """
    return AGENT_REGISTRY.get(agent_type)

def get_available_agent_types() -> list:
    """
    Get list of available agent types.
    
    Returns:
        List of agent type strings
    """
    return list(AGENT_REGISTRY.keys())

def create_agent(agent_type: str, orchestrator=None):
    """
    Create an agent instance by type.
    
    Args:
        agent_type: Type of agent to create
        orchestrator: Agent orchestrator instance
        
    Returns:
        Agent instance or None if type not found
    """
    agent_class = get_agent_class(agent_type)
    if agent_class:
        return agent_class(orchestrator)
    return None