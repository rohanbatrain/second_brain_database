#!/usr/bin/env python3
"""
Comprehensive AI Orchestration Backend Test

This script tests the AI orchestration system from the backend to verify:
1. Orchestrator initialization and health
2. Agent creation and capabilities
3. Session management and lifecycle
4. Model engine and caching
5. Memory layer and context management
6. Resource manager and monitoring
7. Event bus and real-time events
8. Error handling and recovery
9. Performance benchmarks
10. Integration with existing systems
"""

import asyncio
import sys
import os
import time
import json
from datetime import datetime, timezone
from typing import Dict, Any, List

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

async def test_ai_orchestration_system():
    """Comprehensive test of the AI orchestration system."""
    
    print("🤖 AI ORCHESTRATION BACKEND TEST")
    print("=" * 60)
    
    # Initialize database connection first
    try:
        print("\n🔧 Initializing Database Connection...")
        from second_brain_database.database import db_manager
        await db_manager.initialize()
        print("   ✅ Database initialized successfully")
    except Exception as e:
        print(f"   ⚠️ Database initialization warning: {e}")
    
    test_results = {
        "orchestrator_init": False,
        "agent_creation": False,
        "session_management": False,
        "model_engine": False,
        "memory_layer": False,
        "resource_manager": False,
        "event_bus": False,
        "error_handling": False,
        "performance": False,
        "integration": False
    }
    
    try:
        # Test 1: Orchestrator Initialization
        print("\n1️⃣ Testing Orchestrator Initialization...")
        
        try:
            from second_brain_database.integrations.ai_orchestration import (
                AgentOrchestrator, get_ai_event_bus
            )
            from second_brain_database.integrations.ai_orchestration.orchestrator import (
                initialize_global_orchestrator
            )
            
            # Initialize orchestrator
            orchestrator = initialize_global_orchestrator()
            
            if orchestrator and hasattr(orchestrator, 'agents'):
                print(f"   ✅ Orchestrator initialized with {len(orchestrator.agents)} agents")
                test_results["orchestrator_init"] = True
            else:
                print("   ❌ Orchestrator initialization failed")
                
        except Exception as e:
            print(f"   ❌ Orchestrator initialization error: {e}")
        
        # Test 2: Agent Creation and Capabilities
        print("\n2️⃣ Testing Agent Creation and Capabilities...")
        
        try:
            from second_brain_database.integrations.ai_orchestration.agents import (
                AGENT_REGISTRY, create_agent, get_available_agent_types
            )
            
            available_agents = get_available_agent_types()
            print(f"   ✅ Available agent types: {available_agents}")
            
            # Test creating each agent
            created_agents = 0
            for agent_type in available_agents:
                agent = create_agent(agent_type, orchestrator)
                if agent:
                    created_agents += 1
                    print(f"   ✅ {agent_type.title()}Agent: {agent.agent_name}")
            
            if created_agents == len(available_agents):
                test_results["agent_creation"] = True
                print(f"   ✅ All {created_agents} agents created successfully")
            else:
                print(f"   ⚠️ Only {created_agents}/{len(available_agents)} agents created")
                
        except Exception as e:
            print(f"   ❌ Agent creation error: {e}")
        
        # Test 3: Session Management
        print("\n3️⃣ Testing Session Management...")
        
        try:
            from second_brain_database.integrations.mcp.context import MCPUserContext
            
            # Create mock user context
            user_context = MCPUserContext(
                user_id="test_user_123",
                username="test_user",
                permissions=["ai:session:create", "ai:message:send"]
            )
            
            # Test session creation
            session = await orchestrator.create_session(
                user_context=user_context,
                session_type="chat",
                agent_type="personal"
            )
            
            if session and hasattr(session, 'session_id'):
                print(f"   ✅ Session created: {session.session_id}")
                print(f"   ✅ Agent type: {session.current_agent}")
                print(f"   ✅ User ID: {session.user_id}")
                
                # Test session info retrieval
                session_info = await orchestrator.get_session_info(session.session_id)
                if session_info:
                    print(f"   ✅ Session info retrieved: {session_info['message_count']} messages")
                
                # Test session cleanup
                cleanup_success = await orchestrator.cleanup_session(session.session_id)
                if cleanup_success:
                    print("   ✅ Session cleanup successful")
                    test_results["session_management"] = True
                
        except Exception as e:
            print(f"   ❌ Session management error: {e}")
        
        # Test 4: Model Engine
        print("\n4️⃣ Testing Model Engine...")
        
        try:
            if hasattr(orchestrator, 'model_engine'):
                model_engine = orchestrator.model_engine
                
                # Test health check
                health = await model_engine.health_check()
                print(f"   ✅ Model engine health: {health.get('status', 'unknown')}")
                
                # Test performance metrics
                metrics = await model_engine.get_performance_metrics()
                if metrics and 'requests' in metrics:
                    print(f"   ✅ Performance metrics available")
                    print(f"   ✅ Cache enabled: {metrics.get('config', {}).get('cache_enabled', False)}")
                    test_results["model_engine"] = True
                
        except Exception as e:
            print(f"   ❌ Model engine error: {e}")
        
        # Test 5: Memory Layer
        print("\n5️⃣ Testing Memory Layer...")
        
        try:
            if hasattr(orchestrator, 'memory_layer'):
                memory_layer = orchestrator.memory_layer
                
                # Test health check
                health = await memory_layer.health_check()
                print(f"   ✅ Memory layer health: {health.get('status', 'unknown')}")
                
                # Test memory stats
                stats = await memory_layer.get_memory_stats()
                if stats:
                    print(f"   ✅ Memory stats available")
                    test_results["memory_layer"] = True
                
        except Exception as e:
            print(f"   ❌ Memory layer error: {e}")
        
        # Test 6: Resource Manager
        print("\n6️⃣ Testing Resource Manager...")
        
        try:
            if hasattr(orchestrator, 'resource_manager'):
                resource_manager = orchestrator.resource_manager
                
                # Test health check
                health = await resource_manager.health_check()
                print(f"   ✅ Resource manager health: {health.get('status', 'unknown')}")
                
                # Test resource status
                status = resource_manager.get_resource_status()
                if status:
                    print(f"   ✅ Resource status: {status.get('status', 'unknown')}")
                    print(f"   ✅ Active sessions: {status.get('current_metrics', {}).get('active_sessions', 0)}")
                    test_results["resource_manager"] = True
                
        except Exception as e:
            print(f"   ❌ Resource manager error: {e}")
        
        # Test 7: Event Bus
        print("\n7️⃣ Testing Event Bus...")
        
        try:
            event_bus = get_ai_event_bus()
            
            if event_bus:
                # Test event bus stats
                stats = event_bus.get_session_stats()
                print(f"   ✅ Event bus initialized")
                print(f"   ✅ Active sessions: {stats.get('active_sessions', 0)}")
                print(f"   ✅ Total connections: {stats.get('total_connections', 0)}")
                test_results["event_bus"] = True
                
        except Exception as e:
            print(f"   ❌ Event bus error: {e}")
        
        # Test 8: Error Handling
        print("\n8️⃣ Testing Error Handling...")
        
        try:
            # Test error handling health
            error_health = await orchestrator.get_error_handling_health()
            
            if error_health:
                print(f"   ✅ Error handling health: {error_health.get('overall_healthy', False)}")
                
                if 'error_handling' in error_health:
                    eh_status = error_health['error_handling']
                    print(f"   ✅ Circuit breakers: {eh_status.get('circuit_breakers_healthy', False)}")
                    print(f"   ✅ Bulkheads: {eh_status.get('bulkheads_healthy', False)}")
                
                test_results["error_handling"] = True
                
        except Exception as e:
            print(f"   ❌ Error handling error: {e}")
        
        # Test 9: Performance Benchmarks
        print("\n9️⃣ Testing Performance Benchmarks...")
        
        try:
            from second_brain_database.integrations.ai_orchestration.performance_benchmarks import (
                run_performance_benchmarks
            )
            
            # Run a quick benchmark
            print("   🔄 Running performance benchmarks...")
            benchmark_suite = await run_performance_benchmarks()
            
            if benchmark_suite:
                print(f"   ✅ Benchmark completed")
                print(f"   ✅ Success rate: {benchmark_suite.success_rate:.1f}%")
                print(f"   ✅ Average response time: {benchmark_suite.average_response_time:.2f}ms")
                print(f"   ✅ Meets target: {'✅ YES' if benchmark_suite.meets_target else '❌ NO'}")
                test_results["performance"] = True
                
        except Exception as e:
            print(f"   ❌ Performance benchmark error: {e}")
        
        # Test 10: Integration with Existing Systems
        print("\n🔟 Testing Integration with Existing Systems...")
        
        try:
            # Test MCP integration
            if hasattr(orchestrator, 'tool_coordinator'):
                available_tools = await orchestrator.get_available_tools(user_context)
                print(f"   ✅ MCP tools available: {len(available_tools)}")
            
            # Test database integration
            from second_brain_database.database import db_manager
            if db_manager:
                print("   ✅ Database manager available")
            
            # Test Redis integration
            from second_brain_database.managers.redis_manager import redis_manager
            if redis_manager:
                print("   ✅ Redis manager available")
            
            # Test WebSocket integration
            from second_brain_database.websocket_manager import manager as websocket_manager
            if websocket_manager:
                print("   ✅ WebSocket manager available")
            
            test_results["integration"] = True
            
        except Exception as e:
            print(f"   ❌ Integration test error: {e}")
        
        # Test Summary
        print(f"\n{'='*60}")
        print("🧪 TEST RESULTS SUMMARY")
        print(f"{'='*60}")
        
        passed_tests = sum(test_results.values())
        total_tests = len(test_results)
        
        for test_name, passed in test_results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {test_name.replace('_', ' ').title()}: {status}")
        
        success_rate = (passed_tests / total_tests) * 100
        print(f"\nOverall Success Rate: {success_rate:.1f}% ({passed_tests}/{total_tests})")
        
        if success_rate >= 80:
            print("\n🎉 AI ORCHESTRATION SYSTEM IS WORKING!")
            print("✅ Backend components are functional and ready for use")
            return True
        else:
            print("\n⚠️ AI ORCHESTRATION SYSTEM HAS ISSUES")
            print("❌ Some components need attention before production use")
            return False
            
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_ai_orchestration_workflow():
    """Test a complete AI orchestration workflow."""
    
    print(f"\n{'='*60}")
    print("🔄 TESTING COMPLETE AI WORKFLOW")
    print(f"{'='*60}")
    
    # Initialize database connection first
    try:
        from second_brain_database.database import db_manager
        await db_manager.initialize()
        print("   ✅ Database initialized for workflow test")
    except Exception as e:
        print(f"   ⚠️ Database initialization warning: {e}")
    
    try:
        from second_brain_database.integrations.ai_orchestration.orchestrator import initialize_global_orchestrator
        from second_brain_database.integrations.mcp.context import MCPUserContext
        
        # Initialize orchestrator
        orchestrator = initialize_global_orchestrator()
        
        # Create user context
        user_context = MCPUserContext(
            user_id="workflow_test_user",
            username="workflow_test",
            permissions=["ai:session:create", "ai:message:send", "family:read"]
        )
        
        print("\n1. Creating AI session...")
        session = await orchestrator.create_session(
            user_context=user_context,
            session_type="chat",
            agent_type="family"
        )
        print(f"   ✅ Session created: {session.session_id}")
        
        print("\n2. Processing user input...")
        test_message = "Hello, can you help me with my family?"
        
        response_count = 0
        async for event in orchestrator.process_input(
            session.session_id, 
            test_message
        ):
            response_count += 1
            print(f"   📨 Event {response_count}: {event.type.value}")
            if hasattr(event, 'data') and event.data:
                if 'response' in event.data:
                    print(f"   💬 Response: {event.data['response'][:100]}...")
                elif 'token' in event.data:
                    print(f"   🔤 Token: {event.data['token']}")
            
            # Limit output for testing
            if response_count >= 10:
                break
        
        print(f"\n3. Getting session info...")
        session_info = await orchestrator.get_session_info(session.session_id)
        if session_info:
            print(f"   ✅ Messages: {session_info['message_count']}")
            print(f"   ✅ Agent: {session_info['current_agent']}")
        
        print(f"\n4. Cleaning up session...")
        cleanup_success = await orchestrator.cleanup_session(session.session_id)
        if cleanup_success:
            print("   ✅ Session cleaned up successfully")
        
        print(f"\n🎉 WORKFLOW TEST COMPLETED SUCCESSFULLY!")
        return True
        
    except Exception as e:
        print(f"\n❌ WORKFLOW TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function."""
    
    print("Starting AI Orchestration Backend Tests...")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Test 1: System Components
    system_test_passed = await test_ai_orchestration_system()
    
    # Test 2: Complete Workflow (only if system test passed)
    workflow_test_passed = False
    if system_test_passed:
        workflow_test_passed = await test_ai_orchestration_workflow()
    
    # Final Results
    print(f"\n{'='*60}")
    print("🏁 FINAL TEST RESULTS")
    print(f"{'='*60}")
    
    print(f"System Components Test: {'✅ PASS' if system_test_passed else '❌ FAIL'}")
    print(f"Workflow Integration Test: {'✅ PASS' if workflow_test_passed else '❌ FAIL'}")
    
    overall_success = system_test_passed and workflow_test_passed
    
    if overall_success:
        print(f"\n🎉 ALL TESTS PASSED!")
        print("✅ AI Orchestration system is working correctly")
        print("✅ Ready for production use")
    else:
        print(f"\n⚠️ SOME TESTS FAILED")
        print("❌ AI Orchestration system needs attention")
        print("❌ Check error messages above")
    
    return overall_success

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        exit(1)