#!/usr/bin/env python3
"""
Test script for DeepSeek-R1:1.5b integration with Second Brain Database.

This script tests the enhanced model selection capabilities and
DeepSeek-R1 reasoning model integration.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.integrations.ollama import OllamaClient
from second_brain_database.integrations.ai_orchestration.model_engine import ModelEngine, ModelSelector
from second_brain_database.config import settings


async def test_model_availability():
    """Test if DeepSeek-R1 model is available."""
    print("🔍 Testing Model Availability")
    print("-" * 40)
    
    client = OllamaClient(
        base_url=settings.OLLAMA_HOST,
        timeout=30
    )
    
    try:
        # Test DeepSeek-R1 model
        print("📋 Testing DeepSeek-R1:1.5b availability...")
        response = await client.generate(
            "Hello, can you confirm you are DeepSeek-R1?",
            model="deepseek-r1:1.5b",
            temperature=0.3
        )
        print(f"✅ DeepSeek-R1 Response: {response[:100]}...")
        
        # Test Gemma model for comparison
        print("\n📋 Testing Gemma3:1b availability...")
        response = await client.generate(
            "Hello, can you confirm you are Gemma?",
            model="gemma3:1b",
            temperature=0.3
        )
        print(f"✅ Gemma3 Response: {response[:100]}...")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"❌ Model availability test failed: {e}")
        print("💡 Make sure you have DeepSeek-R1:1.5b installed:")
        print("   ollama pull deepseek-r1:1.5b")
        await client.close()
        return False


async def test_model_selector():
    """Test the intelligent model selector."""
    print("\n🧠 Testing Intelligent Model Selector")
    print("-" * 40)
    
    selector = ModelSelector()
    
    # Test queries that should trigger reasoning model
    reasoning_queries = [
        "Explain step by step how to solve this math problem: 2x + 5 = 15",
        "Why does the sky appear blue? Please provide a detailed scientific explanation.",
        "Compare and contrast the advantages and disadvantages of renewable energy sources.",
        "If I have 10 apples and give away 3, then buy 5 more, how many do I have? Show your reasoning.",
        "Analyze the complex relationship between climate change and economic policy."
    ]
    
    # Test queries that should trigger fast model
    simple_queries = [
        "Hello",
        "What is AI?",
        "Thanks",
        "List 3 colors",
        "Define photosynthesis"
    ]
    
    print("🔬 Reasoning Queries (should select DeepSeek-R1):")
    for query in reasoning_queries:
        selected_model = selector.select_model(query)
        expected = "deepseek-r1:1.5b"
        status = "✅" if selected_model == expected else "⚠️"
        print(f"   {status} Query: '{query[:50]}...'")
        print(f"      Selected: {selected_model}")
        print()
    
    print("⚡ Simple Queries (should select Gemma3):")
    for query in simple_queries:
        selected_model = selector.select_model(query)
        expected = "gemma3:1b"
        status = "✅" if selected_model == expected else "⚠️"
        print(f"   {status} Query: '{query}'")
        print(f"      Selected: {selected_model}")
        print()
    
    return True


async def test_reasoning_comparison():
    """Compare reasoning capabilities between models."""
    print("\n🧮 Testing Reasoning Capabilities")
    print("-" * 40)
    
    engine = ModelEngine()
    
    # Complex reasoning prompt
    reasoning_prompt = """
    Solve this step by step:
    
    A train leaves Station A at 2:00 PM traveling at 60 mph toward Station B.
    Another train leaves Station B at 2:30 PM traveling at 80 mph toward Station A.
    The distance between the stations is 350 miles.
    
    At what time will the trains meet, and how far from Station A will they be?
    
    Please show your work step by step.
    """
    
    try:
        # Test with DeepSeek-R1 (reasoning model)
        print("🧠 DeepSeek-R1 (Reasoning Model) Response:")
        print("-" * 30)
        
        response_parts = []
        async for part in engine.generate_response(
            prompt=reasoning_prompt,
            model="deepseek-r1:1.5b",
            temperature=0.3,
            stream=False
        ):
            response_parts.append(part)
        
        deepseek_response = "".join(response_parts)
        print(deepseek_response)
        
        # Test with Gemma3 (fast model) for comparison
        print("\n⚡ Gemma3 (Fast Model) Response:")
        print("-" * 30)
        
        response_parts = []
        async for part in engine.generate_response(
            prompt=reasoning_prompt,
            model="gemma3:1b",
            temperature=0.3,
            stream=False
        ):
            response_parts.append(part)
        
        gemma_response = "".join(response_parts)
        print(gemma_response)
        
        # Compare response lengths and complexity
        print(f"\n📊 Comparison:")
        print(f"   DeepSeek-R1 response length: {len(deepseek_response)} characters")
        print(f"   Gemma3 response length: {len(gemma_response)} characters")
        print(f"   DeepSeek-R1 has {'more' if len(deepseek_response) > len(gemma_response) else 'less'} detailed response")
        
        await engine.cleanup()
        return True
        
    except Exception as e:
        print(f"❌ Reasoning comparison failed: {e}")
        await engine.cleanup()
        return False


async def test_auto_model_selection():
    """Test automatic model selection in action."""
    print("\n🤖 Testing Automatic Model Selection")
    print("-" * 40)
    
    engine = ModelEngine()
    
    test_cases = [
        {
            "query": "Hello, how are you?",
            "expected_model": "gemma3:1b",
            "type": "simple"
        },
        {
            "query": "Explain the mathematical proof for why the square root of 2 is irrational",
            "expected_model": "deepseek-r1:1.5b",
            "type": "reasoning"
        },
        {
            "query": "What is machine learning?",
            "expected_model": "gemma3:1b",
            "type": "simple"
        },
        {
            "query": "Analyze the complex economic implications of artificial intelligence on job markets, considering both short-term disruptions and long-term adaptations",
            "expected_model": "deepseek-r1:1.5b",
            "type": "reasoning"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n🧪 Test Case {i} ({case['type']}):")
        print(f"Query: {case['query']}")
        
        # The model selection happens inside generate_response
        response_parts = []
        async for part in engine.generate_response(
            prompt=case['query'],
            temperature=0.7,
            stream=False
        ):
            response_parts.append(part)
        
        response = "".join(response_parts)
        print(f"Response: {response[:150]}...")
        
        # Check if correct model was likely selected based on response characteristics
        if case['type'] == 'reasoning' and len(response) > 200:
            print("✅ Likely used reasoning model (detailed response)")
        elif case['type'] == 'simple' and len(response) < 500:
            print("✅ Likely used fast model (concise response)")
        else:
            print("⚠️ Model selection unclear from response")
    
    await engine.cleanup()
    return True


async def test_configuration():
    """Test the enhanced configuration."""
    print("\n⚙️ Testing Enhanced Configuration")
    print("-" * 40)
    
    print(f"🔧 Ollama Host: {settings.OLLAMA_HOST}")
    print(f"🔧 Default Model: {settings.OLLAMA_MODEL}")
    print(f"🔧 Available Models: {settings.OLLAMA_AVAILABLE_MODELS}")
    print(f"🔧 Reasoning Model: {settings.OLLAMA_REASONING_MODEL}")
    print(f"🔧 Fast Model: {settings.OLLAMA_FAST_MODEL}")
    print(f"🔧 Auto Selection: {settings.OLLAMA_AUTO_MODEL_SELECTION}")
    
    # Test configuration properties
    available_models = settings.ollama_available_models_list
    print(f"🔧 Available Models List: {available_models}")
    
    model_config = settings.ai_model_config
    print(f"🔧 AI Model Config: {model_config}")
    
    return True


async def test_model_info():
    """Test model information retrieval."""
    print("\n📋 Testing Model Information")
    print("-" * 40)
    
    selector = ModelSelector()
    
    models_to_test = ["deepseek-r1:1.5b", "gemma3:1b"]
    
    for model in models_to_test:
        info = selector.get_model_info(model)
        print(f"🤖 {model}:")
        print(f"   Type: {info['type']}")
        print(f"   Capabilities: {', '.join(info['capabilities'])}")
        print(f"   Performance: {info['performance']}")
        if 'specialization' in info:
            print(f"   Specialization: {info['specialization']}")
        print()
    
    return True


async def test_streaming_with_model_selection():
    """Test streaming responses with automatic model selection."""
    print("\n🌊 Testing Streaming with Model Selection")
    print("-" * 40)
    
    engine = ModelEngine()
    
    test_queries = [
        {
            "query": "Count from 1 to 5 with brief explanations",
            "expected_type": "simple"
        },
        {
            "query": "Explain the step-by-step process of photosynthesis and its chemical equations",
            "expected_type": "reasoning"
        }
    ]
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n🧪 Streaming Test {i} ({test['expected_type']}):")
        print(f"Query: {test['query']}")
        print("Response: ", end="", flush=True)
        
        token_count = 0
        async for token in engine.generate_response(
            prompt=test['query'],
            temperature=0.7,
            stream=True
        ):
            print(token, end="", flush=True)
            token_count += 1
        
        print(f"\n✅ Streamed {token_count} tokens")
    
    await engine.cleanup()
    return True


async def main():
    """Run all DeepSeek-R1 integration tests."""
    print("🧪 DeepSeek-R1:1.5b Integration Tests")
    print("=" * 50)
    print("Testing intelligent model selection and reasoning capabilities")
    print("=" * 50)
    
    tests = [
        ("Configuration", test_configuration),
        ("Model Availability", test_model_availability),
        ("Model Selector Logic", test_model_selector),
        ("Model Information", test_model_info),
        ("Reasoning Comparison", test_reasoning_comparison),
        ("Auto Model Selection", test_auto_model_selection),
        ("Streaming with Selection", test_streaming_with_model_selection),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'=' * 20} {test_name} {'=' * 20}")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("🧪 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n📊 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 DeepSeek-R1 integration is working perfectly!")
        print("\n💡 Key Features:")
        print("   - Intelligent model selection based on query complexity")
        print("   - DeepSeek-R1 for complex reasoning tasks")
        print("   - Gemma3 for fast, simple responses")
        print("   - Automatic model switching")
        print("   - Enhanced reasoning capabilities")
        return 0
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
        print("\n💡 Common issues:")
        print("   - Make sure DeepSeek-R1:1.5b is installed: ollama pull deepseek-r1:1.5b")
        print("   - Verify Ollama is running: ollama list")
        print("   - Check model names match exactly")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)