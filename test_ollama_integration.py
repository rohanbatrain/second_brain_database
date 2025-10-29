#!/usr/bin/env python3
"""
Test script for Ollama integration with Second Brain Database.

This script tests the Ollama integration to ensure it's working properly
with the available models and configuration.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.integrations.ollama import OllamaClient
from second_brain_database.integrations.ai_orchestration.model_engine import ModelEngine
from second_brain_database.config import settings


async def test_basic_ollama_client():
    """Test basic Ollama client functionality."""
    print("🔍 Testing basic Ollama client...")
    
    client = OllamaClient(
        base_url=settings.OLLAMA_HOST,
        model=settings.OLLAMA_MODEL,
        timeout=30
    )
    
    try:
        # Test simple generation
        prompt = "Hello! Please respond with a brief greeting."
        print(f"📝 Sending prompt: {prompt}")
        
        response = await client.generate(prompt, temperature=0.7)
        print(f"✅ Response: {response}")
        
        # Test streaming generation
        print("\n🌊 Testing streaming generation...")
        stream_response = ""
        async for token in client.stream_generate(prompt, temperature=0.7):
            stream_response += token
            print(token, end="", flush=True)
        
        print(f"\n✅ Streaming complete. Total response: {len(stream_response)} characters")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"❌ Basic client test failed: {e}")
        await client.close()
        return False


async def test_model_engine():
    """Test the enhanced model engine."""
    print("\n🚀 Testing enhanced model engine...")
    
    engine = ModelEngine()
    
    try:
        # Test health check
        health = await engine.health_check()
        print(f"🏥 Health check: {health['status']}")
        print(f"   - Client pool size: {health['client_pool_size']}")
        print(f"   - Model available: {health.get('model_available', 'unknown')}")
        
        # Test response generation
        prompt = "What is artificial intelligence? Please provide a brief explanation."
        print(f"\n📝 Testing response generation with prompt: {prompt}")
        
        response_parts = []
        async for part in engine.generate_response(
            prompt=prompt,
            temperature=0.7,
            use_cache=True,
            stream=False
        ):
            response_parts.append(part)
        
        full_response = "".join(response_parts)
        print(f"✅ Generated response ({len(full_response)} chars): {full_response[:200]}...")
        
        # Test streaming response
        print("\n🌊 Testing streaming response...")
        stream_parts = []
        async for part in engine.generate_response(
            prompt="Count from 1 to 5 with brief explanations.",
            temperature=0.5,
            stream=True
        ):
            stream_parts.append(part)
            print(part, end="", flush=True)
        
        print(f"\n✅ Streaming response complete ({len(''.join(stream_parts))} chars)")
        
        # Test performance metrics
        metrics = await engine.get_performance_metrics()
        print(f"\n📊 Performance metrics:")
        print(f"   - Total requests: {metrics['requests']['total']}")
        print(f"   - Cache hit rate: {metrics['requests']['cache_hit_rate']:.1f}%")
        print(f"   - Avg response time: {metrics['performance']['avg_response_time_ms']:.1f}ms")
        print(f"   - Total tokens: {metrics['performance']['total_tokens_generated']}")
        
        await engine.cleanup()
        return True
        
    except Exception as e:
        print(f"❌ Model engine test failed: {e}")
        await engine.cleanup()
        return False


async def test_model_warming():
    """Test model warming functionality."""
    print("\n🔥 Testing model warming...")
    
    engine = ModelEngine()
    
    try:
        # Test warming the current model
        model = settings.OLLAMA_MODEL
        print(f"🔥 Warming model: {model}")
        
        success = await engine.warm_model(model)
        if success:
            print(f"✅ Model {model} warmed successfully")
        else:
            print(f"⚠️ Model {model} warming failed")
        
        # Check metrics after warming
        metrics = await engine.get_performance_metrics()
        warmed_models = metrics['models']['warmed_models']
        print(f"🔥 Warmed models: {warmed_models}")
        
        await engine.cleanup()
        return success
        
    except Exception as e:
        print(f"❌ Model warming test failed: {e}")
        await engine.cleanup()
        return False


async def test_configuration():
    """Test configuration values."""
    print("\n⚙️ Testing configuration...")
    
    print(f"🔧 Ollama Host: {settings.OLLAMA_HOST}")
    print(f"🔧 Ollama Model: {settings.OLLAMA_MODEL}")
    print(f"🔧 AI Enabled: {settings.AI_ENABLED}")
    print(f"🔧 AI Model Pool Size: {settings.AI_MODEL_POOL_SIZE}")
    print(f"🔧 AI Cache Enabled: {settings.AI_CACHE_ENABLED}")
    print(f"🔧 AI Streaming Enabled: {settings.AI_MODEL_STREAMING_ENABLED}")
    
    # Test AI model config property
    model_config = settings.ai_model_config
    print(f"🔧 Model Config: {model_config}")
    
    # Test AI performance config property
    perf_config = settings.ai_performance_config
    print(f"🔧 Performance Config: {perf_config}")
    
    return True


async def main():
    """Run all tests."""
    print("🧪 Starting Ollama Integration Tests")
    print("=" * 50)
    
    tests = [
        ("Configuration", test_configuration),
        ("Basic Ollama Client", test_basic_ollama_client),
        ("Model Engine", test_model_engine),
        ("Model Warming", test_model_warming),
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
        print("🎉 All tests passed! Ollama integration is working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
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