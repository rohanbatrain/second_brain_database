#!/usr/bin/env python3
"""
Simple Ollama Demo for Second Brain Database

This script demonstrates basic Ollama integration without the complex
agent orchestration system, showing how to use Ollama directly.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.integrations.ollama import OllamaClient
from second_brain_database.integrations.ai_orchestration.model_engine import ModelEngine
from second_brain_database.config import settings


async def simple_chat_demo():
    """Simple chat demonstration with Ollama."""
    print("💬 Simple Chat Demo with Ollama")
    print("=" * 40)
    print(f"Using model: {settings.OLLAMA_MODEL}")
    print(f"Host: {settings.OLLAMA_HOST}")
    print("=" * 40)
    
    # Create Ollama client
    client = OllamaClient(
        base_url=settings.OLLAMA_HOST,
        model=settings.OLLAMA_MODEL,
        timeout=30
    )
    
    try:
        # Predefined conversation
        conversation = [
            "Hello! What can you help me with?",
            "Can you explain what a second brain is in the context of knowledge management?",
            "What are some practical tips for organizing digital information?",
            "How can AI assistants help with personal productivity?",
            "Thank you for the helpful information!"
        ]
        
        for i, user_message in enumerate(conversation, 1):
            print(f"\n👤 User ({i}/{len(conversation)}): {user_message}")
            print("🤖 Assistant: ", end="", flush=True)
            
            # Get response from Ollama
            response = await client.generate(
                prompt=user_message,
                temperature=0.7
            )
            
            print(response)
            
            # Small delay between messages for readability
            await asyncio.sleep(1)
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"❌ Chat demo failed: {e}")
        await client.close()
        return False


async def streaming_demo():
    """Demonstrate streaming responses."""
    print("\n🌊 Streaming Response Demo")
    print("=" * 40)
    
    client = OllamaClient(
        base_url=settings.OLLAMA_HOST,
        model=settings.OLLAMA_MODEL,
        timeout=30
    )
    
    try:
        prompt = "Write a short story about a person discovering an AI assistant that helps them organize their life. Keep it under 200 words."
        
        print(f"📝 Prompt: {prompt}")
        print("\n🤖 Streaming Response:")
        print("-" * 30)
        
        # Stream the response
        full_response = ""
        async for token in client.stream_generate(prompt, temperature=0.8):
            print(token, end="", flush=True)
            full_response += token
        
        print(f"\n-" * 30)
        print(f"✅ Complete! Generated {len(full_response)} characters")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"❌ Streaming demo failed: {e}")
        await client.close()
        return False


async def model_engine_demo():
    """Demonstrate the enhanced model engine."""
    print("\n🚀 Enhanced Model Engine Demo")
    print("=" * 40)
    
    engine = ModelEngine()
    
    try:
        # Test different use cases
        use_cases = [
            {
                "name": "Creative Writing",
                "prompt": "Write a haiku about artificial intelligence.",
                "temperature": 0.9
            },
            {
                "name": "Technical Explanation",
                "prompt": "Explain what REST APIs are in simple terms.",
                "temperature": 0.3
            },
            {
                "name": "Problem Solving",
                "prompt": "What are 3 ways to improve focus while working from home?",
                "temperature": 0.6
            }
        ]
        
        for case in use_cases:
            print(f"\n📋 {case['name']} (temp: {case['temperature']}):")
            print(f"❓ {case['prompt']}")
            print("🤖 Response: ", end="", flush=True)
            
            response_parts = []
            async for part in engine.generate_response(
                prompt=case['prompt'],
                temperature=case['temperature'],
                stream=False,
                use_cache=True
            ):
                response_parts.append(part)
            
            response = "".join(response_parts)
            print(response)
            
            await asyncio.sleep(0.5)  # Brief pause between requests
        
        # Show performance metrics
        print("\n📊 Performance Metrics:")
        metrics = await engine.get_performance_metrics()
        print(f"   - Total requests: {metrics['requests']['total']}")
        print(f"   - Cache hit rate: {metrics['requests']['cache_hit_rate']:.1f}%")
        print(f"   - Avg response time: {metrics['performance']['avg_response_time_ms']:.1f}ms")
        
        await engine.cleanup()
        return True
        
    except Exception as e:
        print(f"❌ Model engine demo failed: {e}")
        await engine.cleanup()
        return False


async def interactive_demo():
    """Simple interactive demo (optional)."""
    print("\n🎮 Interactive Demo")
    print("=" * 40)
    print("Type 'quit' to exit, or ask any question!")
    
    client = OllamaClient(
        base_url=settings.OLLAMA_HOST,
        model=settings.OLLAMA_MODEL,
        timeout=30
    )
    
    try:
        # For demo purposes, we'll simulate a few interactions
        demo_questions = [
            "What is machine learning?",
            "How does a database work?",
            "What are the benefits of using AI assistants?"
        ]
        
        print("\n🎭 Simulating interactive session with sample questions:")
        
        for question in demo_questions:
            print(f"\n👤 User: {question}")
            print("🤖 Assistant: ", end="", flush=True)
            
            response = await client.generate(
                prompt=question,
                temperature=0.7
            )
            
            print(response)
            await asyncio.sleep(1)
        
        print("\n✅ Interactive demo complete!")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"❌ Interactive demo failed: {e}")
        await client.close()
        return False


async def main():
    """Run all demos."""
    print("🎯 Simple Ollama Integration Demo")
    print("=" * 50)
    print("This demo shows basic Ollama integration capabilities")
    print("without the complex agent orchestration system.")
    print("=" * 50)
    
    demos = [
        ("Simple Chat", simple_chat_demo),
        ("Streaming Response", streaming_demo),
        ("Enhanced Model Engine", model_engine_demo),
        ("Interactive Session", interactive_demo),
    ]
    
    results = []
    
    for demo_name, demo_func in demos:
        try:
            result = await demo_func()
            results.append((demo_name, result))
        except Exception as e:
            print(f"❌ {demo_name} failed with exception: {e}")
            results.append((demo_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Demo Results Summary")
    print("=" * 50)
    
    passed = 0
    for demo_name, result in results:
        status = "✅ SUCCESS" if result else "❌ FAILED"
        print(f"{demo_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} demos completed successfully")
    
    if passed == len(results):
        print("\n🎉 Ollama integration is working perfectly!")
        print("\n💡 Next steps:")
        print("   - Try different models: ollama pull llama3.2")
        print("   - Adjust temperature for creativity (0.1-1.0)")
        print("   - Use streaming for real-time responses")
        print("   - Enable caching for better performance")
        print("   - Integrate with your existing MCP tools")
        return 0
    else:
        print("⚠️ Some demos had issues. Check the output above.")
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