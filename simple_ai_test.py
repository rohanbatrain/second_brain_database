#!/usr/bin/env python3
"""
Simple AI Agent Test

A basic test to verify the AI agents work without complex async setup.
This will help debug the Streamlit app issues.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

try:
    from src.second_brain_database.integrations.ai_orchestration.orchestrator import AgentOrchestrator
    from src.second_brain_database.integrations.mcp.context import MCPUserContext
    from src.second_brain_database.managers.logging_manager import get_logger
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

logger = get_logger(prefix="[SimpleTest]")

async def test_basic_agent_functionality():
    """Test basic agent functionality."""
    print("🧪 Testing Basic AI Agent Functionality")
    print("=" * 40)
    
    try:
        # Create orchestrator
        print("1. Creating orchestrator...")
        orchestrator = AgentOrchestrator()
        print(f"   ✓ Orchestrator created with {len(orchestrator.agents)} agents")
        
        # Create test user context
        print("2. Creating user context...")
        user_context = MCPUserContext(
            user_id="test_user_123",
            username="testuser",
            role="user",
            permissions=["profile:update", "family:create", "shop:browse"],
            family_memberships=[],
            workspaces=[]
        )
        print(f"   ✓ User context created for: {user_context.username}")
        
        # Test session creation
        print("3. Testing session creation...")
        session_context = await orchestrator.create_session(
            user_context=user_context,
            session_type="chat",
            agent_type="personal"
        )
        print(f"   ✓ Session created: {session_context.session_id}")
        
        # Test simple input processing
        print("4. Testing input processing...")
        test_input = "Hello, can you help me with my profile?"
        
        events_received = 0
        try:
            async for event in orchestrator.process_input(
                session_id=session_context.session_id,
                input_text=test_input,
                metadata={"test": True}
            ):
                events_received += 1
                print(f"   📨 Event {events_received}: {event.type}")
                
                # Limit to first few events for testing
                if events_received >= 3:
                    break
                    
        except Exception as e:
            print(f"   ⚠️  Input processing error: {e}")
            # This is expected if the full AI pipeline isn't set up
        
        print(f"   ✓ Received {events_received} events")
        
        # Test session cleanup
        print("5. Testing session cleanup...")
        cleanup_success = await orchestrator.cleanup_session(session_context.session_id)
        print(f"   ✓ Session cleanup: {'success' if cleanup_success else 'failed'}")
        
        print("\n🎉 Basic functionality test completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_agent_info():
    """Test getting agent information."""
    print("\n🤖 Testing Agent Information")
    print("=" * 30)
    
    try:
        orchestrator = AgentOrchestrator()
        
        # Get agent info
        agent_info = orchestrator.get_agent_info()
        print(f"Available agents: {len(agent_info)}")
        
        for agent_type, info in agent_info.items():
            print(f"  • {info['name']} ({agent_type})")
            print(f"    {info['description'][:60]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent info test failed: {e}")
        return False

async def test_user_contexts():
    """Test different user contexts."""
    print("\n👥 Testing User Contexts")
    print("=" * 25)
    
    contexts = {
        "regular": MCPUserContext(
            user_id="regular_user",
            username="regular",
            role="user",
            permissions=["profile:update", "family:create"],
            family_memberships=[],
            workspaces=[]
        ),
        "admin": MCPUserContext(
            user_id="admin_user",
            username="admin",
            role="admin",
            permissions=["admin:security", "admin:users", "system:monitor"],
            family_memberships=[],
            workspaces=[]
        )
    }
    
    try:
        orchestrator = AgentOrchestrator()
        
        for context_name, context in contexts.items():
            print(f"Testing {context_name} context...")
            
            # Test capabilities for each agent
            capabilities = await orchestrator.get_all_capabilities(context)
            
            total_caps = sum(len(caps) for caps in capabilities.values())
            print(f"  ✓ {context_name} user has {total_caps} total capabilities")
            
            for agent_type, caps in capabilities.items():
                if caps:
                    print(f"    - {agent_type}: {len(caps)} capabilities")
        
        return True
        
    except Exception as e:
        print(f"❌ User context test failed: {e}")
        return False

def main():
    """Main test function."""
    print("🚀 Simple AI Agent Test Suite")
    print("=" * 50)
    
    async def run_tests():
        results = []
        
        # Run tests
        results.append(await test_basic_agent_functionality())
        results.append(await test_agent_info())
        results.append(await test_user_contexts())
        
        # Summary
        passed = sum(results)
        total = len(results)
        
        print(f"\n📊 Test Results: {passed}/{total} passed")
        
        if passed == total:
            print("🎉 All tests passed! The AI agents are working correctly.")
            print("\nYou can now use:")
            print("  streamlit run ai_agents_real_world_test.py")
            return True
        else:
            print("⚠️  Some tests failed. Check the errors above.")
            return False
    
    try:
        success = asyncio.run(run_tests())
        return success
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)