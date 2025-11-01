#!/usr/bin/env python3
"""
Test script to verify all imports work correctly for the AI agents testing suite.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

def test_imports():
    """Test all required imports."""
    print("🔍 Testing imports for AI Agents Testing Suite...")
    
    try:
        print("  ✓ Testing basic Python modules...")
        import asyncio
        import json
        import time
        import uuid
        from datetime import datetime, timezone
        from typing import Dict, Any, List, Optional
        from pathlib import Path
        
        print("  ✓ Testing Second Brain Database core modules...")
        from src.second_brain_database.config import settings
        from src.second_brain_database.managers.logging_manager import get_logger
        
        print("  ✓ Testing AI orchestration modules...")
        from src.second_brain_database.integrations.ai_orchestration.orchestrator import AgentOrchestrator
        from src.second_brain_database.integrations.ai_orchestration.models.events import AIEvent, EventType
        
        print("  ✓ Testing MCP context...")
        from src.second_brain_database.integrations.mcp.context import MCPUserContext
        
        print("  ✓ Testing AI models...")
        from src.second_brain_database.models.ai_models import CreateAISessionRequest
        
        print("  ✓ Testing agent modules...")
        from src.second_brain_database.integrations.ai_orchestration.agents import (
            FamilyAssistantAgent,
            PersonalAssistantAgent,
            WorkspaceAgent,
            CommerceAgent,
            SecurityAgent,
            VoiceAgent
        )
        
        print("✅ All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure you're running from the project root directory")
        print("2. Check that all dependencies are installed")
        print("3. Verify the Second Brain Database is properly set up")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_basic_functionality():
    """Test basic functionality of key components."""
    print("\n🧪 Testing basic functionality...")
    
    try:
        print("  ✓ Testing MCPUserContext creation...")
        from src.second_brain_database.integrations.mcp.context import MCPUserContext
        
        user_context = MCPUserContext(
            user_id="test_user",
            username="testuser",
            role="user",
            permissions=["profile:update", "family:create"],
            family_memberships=[],
            workspaces=[]
        )
        
        print(f"    Created user context for: {user_context.username}")
        
        print("  ✓ Testing EventType enum...")
        from src.second_brain_database.integrations.ai_orchestration.models.events import EventType
        
        print(f"    Available event types: {len(list(EventType))}")
        
        print("  ✓ Testing AgentOrchestrator initialization...")
        from src.second_brain_database.integrations.ai_orchestration.orchestrator import AgentOrchestrator
        
        orchestrator = AgentOrchestrator()
        print(f"    Orchestrator created with {len(orchestrator.agents)} agents")
        
        print("✅ Basic functionality tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Functionality test failed: {e}")
        return False

def main():
    """Main test function."""
    print("🤖 AI Agents Testing Suite - Import Verification")
    print("=" * 50)
    
    # Test imports
    imports_ok = test_imports()
    
    if imports_ok:
        # Test basic functionality
        functionality_ok = test_basic_functionality()
        
        if functionality_ok:
            print("\n🎉 All tests passed! The AI Agents Testing Suite should work correctly.")
            print("\nNext steps:")
            print("  python run_ai_agents_test.py")
            print("  streamlit run ai_agents_real_world_test.py")
            return True
        else:
            print("\n⚠️  Imports work but functionality tests failed.")
            print("The testing suite may have limited functionality.")
            return False
    else:
        print("\n❌ Import tests failed. Please fix the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)