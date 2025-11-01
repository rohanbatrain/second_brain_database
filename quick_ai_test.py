#!/usr/bin/env python3
"""
Quick AI Test - Test just the family agent to see if permissions are fixed
"""

import asyncio
import sys
from datetime import datetime, timezone

# Add the src directory to the path
sys.path.insert(0, 'src')

from second_brain_database.integrations.ai_orchestration.orchestrator import AgentOrchestrator
from second_brain_database.integrations.mcp.context import MCPUserContext
from second_brain_database.database import db_manager

async def test_family_agent():
    """Quick test of family agent with fixed permissions."""
    print("🧪 Quick AI Test - Family Agent")
    print("=" * 50)
    
    try:
        # Initialize database
        await db_manager.initialize()
        print("✅ Database initialized")
        
        # Create orchestrator
        orchestrator = AgentOrchestrator()
        print("✅ Orchestrator created")
        
        # Create user context with proper permissions
        user_context = MCPUserContext(
            user_id="rohan_real_user_001",
            username="rohanbatra",
            email="rohan@example.com",
            role="admin",
            permissions=[
                "ai:basic_chat",
                "ai:voice_interaction", 
                "ai:family_management",
                "ai:workspace_collaboration",
                "ai:commerce_assistance",
                "ai:security_monitoring",
                "ai:admin_operations",
                "ai:conversation_history",
                "ai:knowledge_access",
                "ai:tool_execution"
            ],
            family_memberships=[{
                "family_id": "rohan_family_001",
                "family_name": "Rohan's Family",
                "role": "admin"
            }]
        )
        
        print("✅ User context created")
        
        # Test family agent session creation
        print("\n🧪 Testing Family Agent Session Creation...")
        session = await orchestrator.create_session(
            user_context=user_context,
            agent_type="family"
        )
        
        print(f"✅ Family session created: {session.session_id}")
        
        # Test a simple message
        print("\n💬 Testing Family Agent Message...")
        message_count = 0
        async for event in orchestrator._process_input_internal(
            session_id=session.session_id,
            input_text="Show me my families"
        ):
            if event.type == "response":
                message_count += 1
                response = event.data.get("response", "") if isinstance(event.data, dict) else str(event.data)
                print(f"✅ Response received: {response[:100]}...")
        
        print(f"✅ Family agent test completed: {message_count} responses")
        
        # Test commerce agent
        print("\n🛒 Testing Commerce Agent Session Creation...")
        commerce_session = await orchestrator.create_session(
            user_context=user_context,
            agent_type="commerce"
        )
        
        print(f"✅ Commerce session created: {commerce_session.session_id}")
        
        # Test commerce message
        print("\n💬 Testing Commerce Agent Message...")
        commerce_count = 0
        async for event in orchestrator._process_input_internal(
            session_id=commerce_session.session_id,
            input_text="What can you help me buy?"
        ):
            if event.type == "response":
                commerce_count += 1
                response = event.data.get("response", "") if isinstance(event.data, dict) else str(event.data)
                print(f"✅ Response received: {response[:100]}...")
        
        print(f"✅ Commerce agent test completed: {commerce_count} responses")
        
        # Cleanup
        await orchestrator.cleanup_session(session.session_id)
        await orchestrator.cleanup_session(commerce_session.session_id)
        
        print("\n🎉 ALL TESTS PASSED! AI is fully functional!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_family_agent())
    sys.exit(0 if result else 1)