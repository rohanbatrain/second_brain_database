"""
AI Agent Workflows

This module contains pre-built workflows for different agent types.
Each workflow defines a series of steps that agents can execute
using existing MCP tools and system functionality.

Workflows include:
- Family management workflows (creation, invitations, SBD coordination)
- Personal assistant workflows (profile, security, preferences)
- Workspace collaboration workflows (team management, wallets)
- Commerce workflows (shopping, recommendations, purchases)
- Security workflows (monitoring, admin operations)
- Voice workflows (STT/TTS, commands, notifications)
"""

from .family_workflows import FamilyWorkflows
from .personal_workflows import PersonalWorkflows
from .workspace_workflows import WorkspaceWorkflows
from .commerce_workflows import CommerceWorkflows
from .security_workflows import SecurityWorkflows
from .voice_workflows import VoiceWorkflows
from .base_workflow import BaseWorkflow

__all__ = [
    "BaseWorkflow",
    "FamilyWorkflows",
    "PersonalWorkflows",
    "WorkspaceWorkflows", 
    "CommerceWorkflows",
    "SecurityWorkflows",
    "VoiceWorkflows"
]