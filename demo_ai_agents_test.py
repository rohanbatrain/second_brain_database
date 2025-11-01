#!/usr/bin/env python3
"""
AI Agents Testing Demo

Demonstrates how to use the AI agents testing framework programmatically.
Shows examples of testing individual scenarios, multiple agents, and 
analyzing results.

This script can be used as a reference for integrating AI agent testing
into your own applications or CI/CD pipelines.
"""

import asyncio
import json
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

try:
    from ai_agents_real_world_test import AIAgentTester, REAL_WORLD_SCENARIOS, TEST_USER_CONTEXTS
    from src.second_brain_database.managers.logging_manager import get_logger
except ImportError as e:
    print(f"❌ Failed to import required modules: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

logger = get_logger(prefix="[DemoTest]")

async def demo_single_scenario():
    """Demonstrate testing a single scenario."""
    print("🎯 Demo: Testing Single Scenario")
    print("=" * 40)
    
    tester = AIAgentTester()
    
    # Test family agent - create family scenario
    agent_type = "family"
    scenario = REAL_WORLD_SCENARIOS[agent_type]["scenarios"][0]  # First scenario
    user_context = TEST_USER_CONTEXTS["family_member"]
    
    print(f"Testing: {scenario['title']}")
    print(f"Agent: {REAL_WORLD_SCENARIOS[agent_type]['name']}")
    print(f"Inputs: {len(scenario['inputs'])} test inputs")
    print()
    
    try:
        result = await tester.test_agent_scenario(agent_type, scenario, user_context)
        
        print("📊 Results:")
        print(f"  Success: {'✅ Yes' if result['success'] else '❌ No'}")
        print(f"  Execution Time: {result['execution_time']:.2f}s")
        print(f"  Events Received: {result['events_received']}")
        print(f"  Responses: {len(result['responses'])}")
        print(f"  Errors: {len(result['errors'])}")
        
        if result['errors']:
            print("\n⚠️  Errors encountered:")
            for error in result['errors']:
                print(f"    - {error}")
        
        print("\n💬 Sample Response Events:")
        for i, response in enumerate(result['responses'][:2]):  # Show first 2 responses
            print(f"  Input {i+1}: {response['input'][:50]}...")
            print(f"  Events: {response['event_count']}")
            if response['events']:
                for event in response['events'][:2]:  # Show first 2 events
                    print(f"    - {event['type']}: {str(event['data'])[:100]}...")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
    
    print("\n" + "=" * 40 + "\n")

async def demo_multiple_agents():
    """Demonstrate testing multiple agents."""
    print("🤖 Demo: Testing Multiple Agents")
    print("=" * 40)
    
    tester = AIAgentTester()
    
    # Test family and commerce agents
    agents_to_test = ["family", "commerce"]
    
    print(f"Testing agents: {', '.join(agents_to_test)}")
    print()
    
    try:
        results = await tester.run_comprehensive_test(agents_to_test)
        
        print("📊 Overall Results:")
        print(f"  Agents Tested: {len(results['agents_tested'])}")
        print(f"  Total Scenarios: {results['total_scenarios']}")
        print(f"  Success Rate: {results['performance_summary']['success_rate']:.1f}%")
        print(f"  Total Time: {results['performance_summary']['total_execution_time']:.2f}s")
        print(f"  Events/Second: {results['performance_summary']['events_per_second']:.1f}")
        
        print("\n🎯 Agent-by-Agent Results:")
        for agent_type, agent_result in results['agent_results'].items():
            agent_name = agent_result['agent_name']
            success_rate = (agent_result['scenarios_passed'] / 
                           max(agent_result['scenarios_tested'], 1) * 100)
            
            print(f"  {agent_name}:")
            print(f"    Success Rate: {success_rate:.1f}%")
            print(f"    Scenarios: {agent_result['scenarios_passed']}/{agent_result['scenarios_tested']}")
            print(f"    Events: {agent_result['total_events']}")
            print(f"    Time: {agent_result['total_execution_time']:.2f}s")
        
        if results['errors']:
            print("\n⚠️  Errors encountered:")
            for error in results['errors']:
                print(f"    - {error}")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
    
    print("\n" + "=" * 40 + "\n")

async def demo_performance_analysis():
    """Demonstrate performance analysis."""
    print("⚡ Demo: Performance Analysis")
    print("=" * 40)
    
    tester = AIAgentTester()
    
    # Test personal agent multiple times for performance analysis
    agent_type = "personal"
    scenario = REAL_WORLD_SCENARIOS[agent_type]["scenarios"][0]
    user_context = TEST_USER_CONTEXTS["regular_user"]
    
    print(f"Running performance test: {scenario['title']}")
    print("Testing 3 iterations for performance analysis...")
    print()
    
    execution_times = []
    event_counts = []
    
    try:
        for i in range(3):
            print(f"  Iteration {i+1}/3...", end=" ")
            
            result = await tester.test_agent_scenario(agent_type, scenario, user_context)
            
            if result['success']:
                execution_times.append(result['execution_time'])
                event_counts.append(result['events_received'])
                print(f"✅ {result['execution_time']:.2f}s, {result['events_received']} events")
            else:
                print(f"❌ Failed: {', '.join(result['errors'])}")
        
        if execution_times:
            avg_time = sum(execution_times) / len(execution_times)
            min_time = min(execution_times)
            max_time = max(execution_times)
            avg_events = sum(event_counts) / len(event_counts)
            
            print("\n📈 Performance Analysis:")
            print(f"  Average Time: {avg_time:.2f}s")
            print(f"  Min Time: {min_time:.2f}s")
            print(f"  Max Time: {max_time:.2f}s")
            print(f"  Time Variance: {max_time - min_time:.2f}s")
            print(f"  Average Events: {avg_events:.1f}")
            print(f"  Events/Second: {avg_events / avg_time:.1f}")
            
            # Performance assessment
            if avg_time < 2.0:
                print("  Assessment: ✅ Excellent performance")
            elif avg_time < 5.0:
                print("  Assessment: 👍 Good performance")
            else:
                print("  Assessment: ⚠️  Slow performance - needs optimization")
        
    except Exception as e:
        print(f"❌ Performance test failed: {str(e)}")
    
    print("\n" + "=" * 40 + "\n")

async def demo_error_handling():
    """Demonstrate error handling and edge cases."""
    print("🛡️  Demo: Error Handling")
    print("=" * 40)
    
    tester = AIAgentTester()
    
    print("Testing error scenarios and edge cases...")
    print()
    
    # Test 1: Invalid agent type
    print("1. Testing invalid agent type...")
    try:
        result = await tester.test_agent_scenario(
            "invalid_agent", 
            {"title": "Test", "inputs": ["test"], "expected_outcomes": ["test"]},
            TEST_USER_CONTEXTS["regular_user"]
        )
        print(f"   Result: {result['success']}")
    except Exception as e:
        print(f"   ✅ Correctly caught error: {str(e)[:50]}...")
    
    # Test 2: Security agent with regular user (should fail permissions)
    print("2. Testing security agent with regular user permissions...")
    try:
        security_scenario = REAL_WORLD_SCENARIOS["security"]["scenarios"][0]
        result = await tester.test_agent_scenario(
            "security",
            security_scenario,
            TEST_USER_CONTEXTS["regular_user"]  # Regular user, not admin
        )
        
        if not result['success'] and any("permission" in error.lower() for error in result['errors']):
            print("   ✅ Correctly denied access due to insufficient permissions")
        else:
            print("   ⚠️  Security check may not be working properly")
            
    except Exception as e:
        print(f"   ✅ Correctly caught permission error: {str(e)[:50]}...")
    
    # Test 3: Empty input handling
    print("3. Testing empty input handling...")
    try:
        empty_scenario = {
            "title": "Empty Input Test",
            "inputs": [""],
            "expected_outcomes": ["Error handling"]
        }
        result = await tester.test_agent_scenario(
            "personal",
            empty_scenario,
            TEST_USER_CONTEXTS["regular_user"]
        )
        print(f"   Result: {'✅ Handled gracefully' if result['success'] or result['errors'] else '⚠️  Unexpected behavior'}")
        
    except Exception as e:
        print(f"   ✅ Correctly handled empty input: {str(e)[:50]}...")
    
    print("\n" + "=" * 40 + "\n")

async def demo_custom_scenario():
    """Demonstrate creating and testing custom scenarios."""
    print("🎨 Demo: Custom Scenario Testing")
    print("=" * 40)
    
    tester = AIAgentTester()
    
    # Create a custom scenario for the commerce agent
    custom_scenario = {
        "title": "Custom Shopping Workflow",
        "description": "Test a complete shopping workflow from browsing to purchase",
        "inputs": [
            "I want to buy something cool for my profile",
            "Show me avatars under 50 tokens",
            "What's the most popular avatar?",
            "Help me choose between a robot avatar and a fantasy avatar"
        ],
        "expected_outcomes": [
            "Shopping assistance offered",
            "Filtered avatar recommendations",
            "Popularity-based suggestions",
            "Comparison and recommendation"
        ]
    }
    
    print(f"Testing custom scenario: {custom_scenario['title']}")
    print(f"Description: {custom_scenario['description']}")
    print(f"Inputs: {len(custom_scenario['inputs'])} custom inputs")
    print()
    
    try:
        result = await tester.test_agent_scenario(
            "commerce",
            custom_scenario,
            TEST_USER_CONTEXTS["regular_user"]
        )
        
        print("📊 Custom Scenario Results:")
        print(f"  Success: {'✅ Yes' if result['success'] else '❌ No'}")
        print(f"  Execution Time: {result['execution_time']:.2f}s")
        print(f"  Total Events: {result['events_received']}")
        
        print("\n💬 Interaction Flow:")
        for i, response in enumerate(result['responses']):
            print(f"  Step {i+1}: {response['input']}")
            print(f"    Events generated: {response['event_count']}")
            
            # Show sample response content
            for event in response['events']:
                if event['type'] == 'RESPONSE' and 'response' in event['data']:
                    response_text = event['data']['response'][:100]
                    print(f"    Response: {response_text}...")
                    break
        
        if result['errors']:
            print("\n⚠️  Issues encountered:")
            for error in result['errors']:
                print(f"    - {error}")
        
    except Exception as e:
        print(f"❌ Custom scenario test failed: {str(e)}")
    
    print("\n" + "=" * 40 + "\n")

async def main():
    """Run all demo scenarios."""
    print("🚀 AI Agents Testing Framework Demo")
    print("=" * 50)
    print("This demo shows how to use the AI agents testing framework")
    print("for various testing scenarios and use cases.")
    print("=" * 50)
    print()
    
    try:
        # Run all demo scenarios
        await demo_single_scenario()
        await demo_multiple_agents()
        await demo_performance_analysis()
        await demo_error_handling()
        await demo_custom_scenario()
        
        print("🎉 Demo completed successfully!")
        print("\nNext steps:")
        print("- Run the Streamlit app: streamlit run ai_agents_real_world_test.py")
        print("- Use automated testing: python automated_ai_agents_test.py --comprehensive")
        print("- Integrate into your CI/CD pipeline")
        print("- Create custom scenarios for your specific use cases")
        
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {str(e)}")
        logger.error(f"Demo execution failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())