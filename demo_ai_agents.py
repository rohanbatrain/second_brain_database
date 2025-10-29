#!/usr/bin/env python3
"""
Demo script for AI Agent Orchestration with Ollama integration.

This script demonstrates how to use the AI agents in the Second Brain Database
system with your local Ollama installation.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.integrations.ai_orchestration.agents.personal_agent import PersonalAgent
from second_brain_database.integrations.ai_orchestration.agents.family_agent import FamilyAgent
from second_brain_database.integrations.ai_orchestration.agents.workspace_agent import WorkspaceAgent
from second_brain_database.integrations.ai_orchestration.model_engine import ModelEngine
from second_brain_database.config import settings


async def demo_personal_agent():
    """Demonstrate the personal agent capabilities."""
    print("🤖 Personal Agent Demo")
    print("-" * 30)
    
    try:
        agent = PersonalAgent()
        
        # Initialize the agent
        await agent.initialize()
        
        # Demo conversation
        queries = [
            "Hello! Can you help me organize my thoughts?",
            "What are some good productivity tips for working from home?",
            "How can I better manage my time during the day?"
        ]
        
        for query in queries:
            print(f"\n👤 User: {query}")
            print("🤖 Agent: ", end="", flush=True)
            
            response_parts = []
            async for part in agent.process_message(query):
                response_parts.append(part)
                print(part, end="", flush=True)
            
            print()  # New line after response
        
        # Get agent status
        status = await agent.get_status()
        print(f"\n📊 Agent Status: {status}")
        
        await agent.cleanup()
        return True
        
    except Exception as e:
        print(f"❌ Personal agent demo failed: {e}")
        return False


async def demo_family_agent():
    """Demonstrate the family agent capabilities."""
    print("\n👨‍👩‍👧‍👦 Family Agent Demo")
    print("-" * 30)
    
    try:
        agent = FamilyAgent()
        
        # Initialize the agent
        await agent.initialize()
        
        # Demo family-related queries
        queries = [
            "How can I help coordinate family activities better?",
            "What are some good ways to manage family finances?",
            "Can you suggest some family bonding activities?"
        ]
        
        for query in queries:
            print(f"\n👤 User: {query}")
            print("👨‍👩‍👧‍👦 Family Agent: ", end="", flush=True)
            
            response_parts = []
            async for part in agent.process_message(query):
                response_parts.append(part)
                print(part, end="", flush=True)
            
            print()  # New line after response
        
        await agent.cleanup()
        return True
        
    except Exception as e:
        print(f"❌ Family agent demo failed: {e}")
        return False


async def demo_workspace_agent():
    """Demonstrate the workspace agent capabilities."""
    print("\n💼 Workspace Agent Demo")
    print("-" * 30)
    
    try:
        agent = WorkspaceAgent()
        
        # Initialize the agent
        await agent.initialize()
        
        # Demo workspace-related queries
        queries = [
            "How can I improve team collaboration?",
            "What are best practices for project management?",
            "Can you help me organize my workspace better?"
        ]
        
        for query in queries:
            print(f"\n👤 User: {query}")
            print("💼 Workspace Agent: ", end="", flush=True)
            
            response_parts = []
            async for part in agent.process_message(query):
                response_parts.append(part)
                print(part, end="", flush=True)
            
            print()  # New line after response
        
        await agent.cleanup()
        return True
        
    except Exception as e:
        print(f"❌ Workspace agent demo failed: {e}")
        return False


async def demo_model_engine_features():
    """Demonstrate advanced model engine features."""
    print("\n🚀 Model Engine Advanced Features Demo")
    print("-" * 40)
    
    try:
        engine = ModelEngine()
        
        # Test different temperatures
        print("🌡️ Testing different creativity levels (temperature):")
        
        prompt = "Write a creative short story opening about a mysterious door."
        
        temperatures = [0.3, 0.7, 1.0]
        for temp in temperatures:
            print(f"\n🌡️ Temperature {temp} (", end="")
            if temp == 0.3:
                print("Conservative): ", end="")
            elif temp == 0.7:
                print("Balanced): ", end="")
            else:
                print("Creative): ", end="")
            
            response_parts = []
            async for part in engine.generate_response(
                prompt=prompt,
                temperature=temp,
                max_tokens=100,
                stream=False
            ):
                response_parts.append(part)
            
            response = "".join(response_parts)
            print(f"{response[:150]}..." if len(response) > 150 else response)
        
        # Test caching
        print("\n💾 Testing response caching:")
        
        cache_test_prompt = "What is the capital of France?"
        
        # First request (cache miss)
        print("🔍 First request (should be cache miss):")
        start_time = asyncio.get_event_loop().time()
        
        response_parts = []
        async for part in engine.generate_response(
            prompt=cache_test_prompt,
            use_cache=True,
            stream=False
        ):
            response_parts.append(part)
        
        first_time = asyncio.get_event_loop().time() - start_time
        print(f"Response: {''.join(response_parts)}")
        print(f"Time: {first_time:.2f}s")
        
        # Second request (should be cache hit)
        print("\n🎯 Second request (should be cache hit):")
        start_time = asyncio.get_event_loop().time()
        
        response_parts = []
        async for part in engine.generate_response(
            prompt=cache_test_prompt,
            use_cache=True,
            stream=False
        ):
            response_parts.append(part)
        
        second_time = asyncio.get_event_loop().time() - start_time
        print(f"Response: {''.join(response_parts)}")
        print(f"Time: {second_time:.2f}s")
        
        if second_time < first_time:
            print("✅ Caching is working! Second request was faster.")
        else:
            print("⚠️ Cache might not be working as expected.")
        
        # Show performance metrics
        metrics = await engine.get_performance_metrics()
        print(f"\n📊 Performance Metrics:")
        print(f"   - Total requests: {metrics['requests']['total']}")
        print(f"   - Cache hit rate: {metrics['requests']['cache_hit_rate']:.1f}%")
        print(f"   - Average response time: {metrics['performance']['avg_response_time_ms']:.1f}ms")
        print(f"   - Total tokens generated: {metrics['performance']['total_tokens_generated']}")
        
        await engine.cleanup()
        return True
        
    except Exception as e:
        print(f"❌ Model engine features demo failed: {e}")
        return False


async def demo_streaming_vs_complete():
    """Demonstrate streaming vs complete response modes."""
    print("\n🌊 Streaming vs Complete Response Demo")
    print("-" * 40)
    
    try:
        engine = ModelEngine()
        
        prompt = "Explain the benefits of renewable energy in 3 key points."
        
        # Complete response
        print("📄 Complete Response Mode:")
        start_time = asyncio.get_event_loop().time()
        
        response_parts = []
        async for part in engine.generate_response(
            prompt=prompt,
            stream=False
        ):
            response_parts.append(part)
        
        complete_time = asyncio.get_event_loop().time() - start_time
        complete_response = "".join(response_parts)
        print(f"Response: {complete_response}")
        print(f"Time: {complete_time:.2f}s")
        
        # Streaming response
        print("\n🌊 Streaming Response Mode:")
        start_time = asyncio.get_event_loop().time()
        
        print("Response: ", end="", flush=True)
        token_count = 0
        async for part in engine.generate_response(
            prompt=prompt,
            stream=True
        ):
            print(part, end="", flush=True)
            token_count += 1
        
        streaming_time = asyncio.get_event_loop().time() - start_time
        print(f"\nTime: {streaming_time:.2f}s")
        print(f"Tokens streamed: {token_count}")
        
        await engine.cleanup()
        return True
        
    except Exception as e:
        print(f"❌ Streaming demo failed: {e}")
        return False


async def main():
    """Run all demos."""
    print("🎭 AI Agent Orchestration Demo")
    print("=" * 50)
    print(f"Using Ollama model: {settings.OLLAMA_MODEL}")
    print(f"Ollama host: {settings.OLLAMA_HOST}")
    print("=" * 50)
    
    demos = [
        ("Personal Agent", demo_personal_agent),
        ("Family Agent", demo_family_agent),
        ("Workspace Agent", demo_workspace_agent),
        ("Model Engine Features", demo_model_engine_features),
        ("Streaming vs Complete", demo_streaming_vs_complete),
    ]
    
    results = []
    
    for demo_name, demo_func in demos:
        try:
            print(f"\n{'=' * 20} {demo_name} {'=' * 20}")
            result = await demo_func()
            results.append((demo_name, result))
        except Exception as e:
            print(f"❌ {demo_name} failed with exception: {e}")
            results.append((demo_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("🎭 Demo Results Summary")
    print("=" * 50)
    
    passed = 0
    for demo_name, result in results:
        status = "✅ SUCCESS" if result else "❌ FAILED"
        print(f"{demo_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n📊 Overall: {passed}/{len(results)} demos completed successfully")
    
    if passed == len(results):
        print("🎉 All demos completed successfully!")
        print("\n💡 Your Ollama integration is ready for production use!")
        print("   - Try different models by changing OLLAMA_MODEL in config")
        print("   - Adjust temperature for different creativity levels")
        print("   - Use streaming for real-time responses")
        print("   - Enable caching for better performance")
        return 0
    else:
        print("⚠️ Some demos had issues. Check the output above for details.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)