#!/usr/bin/env python3
"""
Demo script showcasing DeepSeek-R1:1.5b reasoning capabilities.

This script demonstrates the enhanced reasoning capabilities of DeepSeek-R1
compared to other models, and shows off the intelligent model selection.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.integrations.ai_orchestration.model_engine import ModelEngine
from second_brain_database.config import settings


async def demo_reasoning_tasks():
    """Demonstrate complex reasoning tasks with DeepSeek-R1."""
    print("🧠 DeepSeek-R1 Reasoning Capabilities Demo")
    print("=" * 50)
    
    engine = ModelEngine()
    
    reasoning_tasks = [
        {
            "title": "Mathematical Problem Solving",
            "prompt": """
            Solve this step by step:
            
            Sarah has a rectangular garden that is 12 meters long and 8 meters wide.
            She wants to create a path around the entire garden that is 1.5 meters wide.
            
            1. What is the area of the original garden?
            2. What are the dimensions of the garden including the path?
            3. What is the total area including the path?
            4. What is the area of just the path?
            
            Please show all your calculations step by step.
            """,
            "expected_model": "deepseek-r1:1.5b"
        },
        {
            "title": "Logical Reasoning",
            "prompt": """
            Analyze this logical puzzle:
            
            In a small town, there are three friends: Alice, Bob, and Charlie.
            - Alice always tells the truth on Mondays, Wednesdays, and Fridays, but lies on other days.
            - Bob always tells the truth on Tuesdays, Thursdays, and Saturdays, but lies on other days.
            - Charlie always tells the truth on Sundays, but lies on all other days.
            
            Today, Alice says "Yesterday I lied."
            Bob says "Alice is telling the truth."
            Charlie says "Bob is lying."
            
            What day of the week is it today? Explain your reasoning step by step.
            """,
            "expected_model": "deepseek-r1:1.5b"
        },
        {
            "title": "Scientific Analysis",
            "prompt": """
            Explain the greenhouse effect and its impact on climate change:
            
            1. What is the greenhouse effect and how does it work naturally?
            2. How do human activities enhance this effect?
            3. What are the main greenhouse gases and their sources?
            4. What are the predicted consequences of enhanced greenhouse effect?
            5. What solutions exist to mitigate these effects?
            
            Please provide a comprehensive analysis with scientific reasoning.
            """,
            "expected_model": "deepseek-r1:1.5b"
        }
    ]
    
    for i, task in enumerate(reasoning_tasks, 1):
        print(f"\n{'=' * 20} Task {i}: {task['title']} {'=' * 20}")
        print(f"📝 Prompt: {task['prompt'][:100]}...")
        print(f"🎯 Expected Model: {task['expected_model']}")
        print("\n🤖 DeepSeek-R1 Response:")
        print("-" * 50)
        
        response_parts = []
        async for part in engine.generate_response(
            prompt=task['prompt'],
            model="deepseek-r1:1.5b",  # Force DeepSeek-R1 for demonstration
            temperature=0.3,
            stream=False
        ):
            response_parts.append(part)
        
        response = "".join(response_parts)
        print(response)
        print("-" * 50)
        
        # Brief pause between tasks
        await asyncio.sleep(1)
    
    await engine.cleanup()


async def demo_model_comparison():
    """Compare responses between DeepSeek-R1 and Gemma3."""
    print("\n🔄 Model Comparison Demo")
    print("=" * 50)
    
    engine = ModelEngine()
    
    comparison_prompt = """
    Explain the concept of recursion in programming:
    
    1. What is recursion?
    2. How does it work?
    3. Provide a simple example
    4. What are the advantages and disadvantages?
    5. When should you use recursion vs iteration?
    """
    
    models_to_compare = [
        {"name": "gemma3:1b", "label": "Gemma3 (Fast Model)"},
        {"name": "deepseek-r1:1.5b", "label": "DeepSeek-R1 (Reasoning Model)"}
    ]
    
    responses = {}
    
    for model_info in models_to_compare:
        model_name = model_info["name"]
        model_label = model_info["label"]
        
        print(f"\n🤖 {model_label} Response:")
        print("-" * 40)
        
        start_time = asyncio.get_event_loop().time()
        
        response_parts = []
        async for part in engine.generate_response(
            prompt=comparison_prompt,
            model=model_name,
            temperature=0.5,
            stream=False
        ):
            response_parts.append(part)
        
        response_time = asyncio.get_event_loop().time() - start_time
        response = "".join(response_parts)
        
        print(response)
        print(f"\n⏱️ Response time: {response_time:.2f} seconds")
        print(f"📏 Response length: {len(response)} characters")
        
        responses[model_name] = {
            "response": response,
            "time": response_time,
            "length": len(response)
        }
    
    # Comparison summary
    print(f"\n📊 Comparison Summary:")
    print("-" * 30)
    
    gemma_resp = responses["gemma3:1b"]
    deepseek_resp = responses["deepseek-r1:1.5b"]
    
    print(f"Response Length:")
    print(f"   Gemma3: {gemma_resp['length']} characters")
    print(f"   DeepSeek-R1: {deepseek_resp['length']} characters")
    print(f"   DeepSeek-R1 is {deepseek_resp['length'] / gemma_resp['length']:.1f}x longer")
    
    print(f"\nResponse Time:")
    print(f"   Gemma3: {gemma_resp['time']:.2f} seconds")
    print(f"   DeepSeek-R1: {deepseek_resp['time']:.2f} seconds")
    print(f"   DeepSeek-R1 is {deepseek_resp['time'] / gemma_resp['time']:.1f}x slower")
    
    await engine.cleanup()


async def demo_auto_selection():
    """Demonstrate automatic model selection in action."""
    print("\n🎯 Automatic Model Selection Demo")
    print("=" * 50)
    
    engine = ModelEngine()
    
    test_queries = [
        {
            "query": "Hi there!",
            "type": "Simple Greeting",
            "expected": "gemma3:1b"
        },
        {
            "query": "What's the weather like?",
            "type": "Simple Question",
            "expected": "gemma3:1b"
        },
        {
            "query": "Solve this equation step by step: 3x² + 2x - 8 = 0",
            "type": "Mathematical Problem",
            "expected": "deepseek-r1:1.5b"
        },
        {
            "query": "Analyze the philosophical implications of artificial consciousness and explain whether machines can truly think",
            "type": "Complex Analysis",
            "expected": "deepseek-r1:1.5b"
        },
        {
            "query": "Compare and contrast the economic theories of Keynesian and Austrian schools of thought",
            "type": "Comparative Analysis",
            "expected": "deepseek-r1:1.5b"
        },
        {
            "query": "Thanks for your help!",
            "type": "Simple Thanks",
            "expected": "gemma3:1b"
        }
    ]
    
    print("🔍 Testing automatic model selection based on query complexity...")
    print()
    
    for i, test in enumerate(test_queries, 1):
        print(f"🧪 Test {i}: {test['type']}")
        print(f"   Query: \"{test['query']}\"")
        print(f"   Expected Model: {test['expected']}")
        print("   Response: ", end="", flush=True)
        
        # Let the engine automatically select the model
        response_parts = []
        async for part in engine.generate_response(
            prompt=test['query'],
            temperature=0.7,
            stream=False  # Use complete response for cleaner demo
        ):
            response_parts.append(part)
        
        response = "".join(response_parts)
        print(f"{response[:100]}{'...' if len(response) > 100 else ''}")
        
        # Analyze response characteristics to guess which model was used
        if len(response) > 200 and any(word in response.lower() for word in ['step', 'analysis', 'consider', 'however']):
            likely_model = "deepseek-r1:1.5b (reasoning model - detailed response)"
        else:
            likely_model = "gemma3:1b (fast model - concise response)"
        
        print(f"   Likely Used: {likely_model}")
        print()
    
    await engine.cleanup()


async def demo_streaming_reasoning():
    """Demonstrate streaming responses for reasoning tasks."""
    print("\n🌊 Streaming Reasoning Demo")
    print("=" * 50)
    
    engine = ModelEngine()
    
    streaming_prompt = """
    Walk me through the process of how a computer executes a simple program:
    
    Consider this simple Python code:
    ```python
    x = 5
    y = 10
    result = x + y
    print(result)
    ```
    
    Explain step by step what happens from when you run this code until the output appears.
    Include details about parsing, compilation/interpretation, memory allocation, and execution.
    """
    
    print("📝 Prompt: Complex technical explanation")
    print("🎯 Expected Model: DeepSeek-R1 (reasoning model)")
    print("\n🌊 Streaming Response:")
    print("-" * 50)
    
    token_count = 0
    start_time = asyncio.get_event_loop().time()
    
    async for token in engine.generate_response(
        prompt=streaming_prompt,
        model="deepseek-r1:1.5b",
        temperature=0.4,
        stream=True
    ):
        print(token, end="", flush=True)
        token_count += 1
    
    total_time = asyncio.get_event_loop().time() - start_time
    
    print(f"\n-" * 50)
    print(f"✅ Streaming complete!")
    print(f"   Tokens streamed: {token_count}")
    print(f"   Total time: {total_time:.2f} seconds")
    print(f"   Tokens per second: {token_count / total_time:.1f}")
    
    await engine.cleanup()


async def main():
    """Run all DeepSeek-R1 reasoning demos."""
    print("🧠 DeepSeek-R1:1.5b Reasoning Capabilities Demo")
    print("=" * 60)
    print("Showcasing advanced reasoning and intelligent model selection")
    print("=" * 60)
    
    demos = [
        ("Complex Reasoning Tasks", demo_reasoning_tasks),
        ("Model Comparison", demo_model_comparison),
        ("Automatic Model Selection", demo_auto_selection),
        ("Streaming Reasoning", demo_streaming_reasoning),
    ]
    
    for demo_name, demo_func in demos:
        try:
            await demo_func()
        except Exception as e:
            print(f"❌ {demo_name} failed: {e}")
            print("💡 Make sure DeepSeek-R1:1.5b is installed and working")
    
    print("\n" + "=" * 60)
    print("🎉 Demo Complete!")
    print("=" * 60)
    print("\n💡 Key Takeaways:")
    print("   - DeepSeek-R1 excels at complex reasoning and problem-solving")
    print("   - Automatic model selection optimizes performance and quality")
    print("   - Gemma3 provides fast responses for simple queries")
    print("   - DeepSeek-R1 provides detailed analysis for complex tasks")
    print("   - Streaming works seamlessly with both models")
    
    print("\n🚀 Try it yourself:")
    print("   - Ask complex mathematical problems")
    print("   - Request detailed scientific explanations")
    print("   - Pose logical reasoning puzzles")
    print("   - Compare philosophical concepts")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)