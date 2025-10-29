#!/usr/bin/env python3
"""
Test script for AI Agent Voice Integration with LiveKit

This script tests the voice integration functionality including:
- LiveKit token generation
- Voice agent initialization
- STT/TTS processing
- Event streaming
"""

import asyncio
import base64
import json
from typing import Dict, Any

from ..mcp.context import MCPUserContext
from .orchestrator import AgentOrchestrator
from .agents.voice_agent import VoiceAgent
from ...config import settings


async def test_voice_agent_initialization():
    """Test voice agent initialization and configuration."""
    print("Testing Voice Agent Initialization...")
    
    try:
        # Create orchestrator
        orchestrator = AgentOrchestrator()
        
        # Get voice agent
        voice_agent = orchestrator.agents.get("voice")
        
        if not voice_agent:
            print("❌ Voice agent not found in orchestrator")
            return False
        
        print(f"✅ Voice agent initialized: {voice_agent.agent_name}")
        print(f"   Description: {voice_agent.agent_description}")
        print(f"   Capabilities: {len(voice_agent.capabilities)}")
        
        # Test LiveKit configuration
        if voice_agent.livekit_api_key and voice_agent.livekit_api_secret:
            print("✅ LiveKit configuration found")
        else:
            print("⚠️  LiveKit not configured (API key/secret missing)")
        
        return True
        
    except Exception as e:
        print(f"❌ Voice agent initialization failed: {e}")
        return False


async def test_livekit_token_generation():
    """Test LiveKit token generation."""
    print("\nTesting LiveKit Token Generation...")
    
    try:
        # Create voice agent
        orchestrator = AgentOrchestrator()
        voice_agent = orchestrator.agents.get("voice")
        
        if not voice_agent:
            print("❌ Voice agent not available")
            return False
        
        # Test token generation
        user_id = "test_user_123"
        token_config = await voice_agent.create_livekit_token(user_id)
        
        if token_config:
            print("✅ LiveKit token generated successfully")
            print(f"   Room: {token_config.get('room', 'N/A')}")
            print(f"   Token length: {len(token_config.get('token', ''))}")
            print(f"   LiveKit URL: {token_config.get('livekit_url', 'N/A')}")
            return True
        else:
            print("⚠️  LiveKit token generation failed (likely not configured)")
            return False
            
    except Exception as e:
        print(f"❌ LiveKit token generation error: {e}")
        return False


async def test_voice_session_setup():
    """Test voice session setup."""
    print("\nTesting Voice Session Setup...")
    
    try:
        # Create orchestrator and session
        orchestrator = AgentOrchestrator()
        
        # Create test user context
        user_context = MCPUserContext(
            user_id="test_user_123",
            username="test_user",
            email="test@example.com",
            role="user",
            permissions=["voice:use", "voice:transcribe"]
        )
        
        # Create session
        session_context = await orchestrator.create_session(
            user_context=user_context,
            session_type="voice",
            agent_type="voice"
        )
        
        print(f"✅ Session created: {session_context.session_id}")
        
        # Enable voice for session
        voice_enabled = await orchestrator.enable_voice_for_session(session_context.session_id)
        
        if voice_enabled:
            print("✅ Voice enabled for session")
        else:
            print("❌ Failed to enable voice for session")
            return False
        
        # Test voice session setup
        voice_agent = orchestrator.agents.get("voice")
        voice_config = await voice_agent.setup_voice_session(session_context.session_id, user_context)
        
        if voice_config:
            print("✅ Voice session setup completed")
            print(f"   Session ID: {voice_config.get('session_id')}")
            print(f"   Voice settings: {voice_config.get('voice_settings', {})}")
            print(f"   Capabilities: {voice_config.get('capabilities', {})}")
            return True
        else:
            print("❌ Voice session setup failed")
            return False
            
    except Exception as e:
        print(f"❌ Voice session setup error: {e}")
        return False


async def test_voice_processing_simulation():
    """Test voice processing with simulated audio data."""
    print("\nTesting Voice Processing Simulation...")
    
    try:
        # Create orchestrator and session
        orchestrator = AgentOrchestrator()
        
        user_context = MCPUserContext(
            user_id="test_user_123",
            username="test_user",
            email="test@example.com",
            role="user",
            permissions=["voice:use", "voice:transcribe"]
        )
        
        session_context = await orchestrator.create_session(
            user_context=user_context,
            session_type="voice",
            agent_type="voice"
        )
        
        # Enable voice
        await orchestrator.enable_voice_for_session(session_context.session_id)
        
        # Simulate audio data (empty bytes for testing)
        simulated_audio = b"simulated_audio_data_for_testing"
        
        print("✅ Simulating voice input processing...")
        
        # Process voice input
        event_count = 0
        async for event in orchestrator.process_voice_input(session_context.session_id, simulated_audio):
            event_count += 1
            print(f"   Event {event_count}: {event.type} - {event.data}")
            
            # Limit events for testing
            if event_count >= 5:
                break
        
        print(f"✅ Voice processing simulation completed ({event_count} events)")
        return True
        
    except Exception as e:
        print(f"❌ Voice processing simulation error: {e}")
        return False


async def test_configuration_validation():
    """Test configuration validation for voice features."""
    print("\nTesting Configuration Validation...")
    
    try:
        config_status = {
            "AI_VOICE_ENABLED": settings.AI_VOICE_ENABLED,
            "AI_VOICE_STT_ENABLED": settings.AI_VOICE_STT_ENABLED,
            "AI_VOICE_TTS_ENABLED": settings.AI_VOICE_TTS_ENABLED,
            "AI_VOICE_REALTIME_ENABLED": settings.AI_VOICE_REALTIME_ENABLED,
            "AI_VOICE_COMMAND_ENABLED": settings.AI_VOICE_COMMAND_ENABLED,
            "VOICE_SAMPLE_RATE": settings.VOICE_SAMPLE_RATE,
            "VOICE_CHUNK_SIZE": settings.VOICE_CHUNK_SIZE,
            "VOICE_MAX_AUDIO_LENGTH": settings.VOICE_MAX_AUDIO_LENGTH,
            "LIVEKIT_API_KEY": "SET" if settings.LIVEKIT_API_KEY else "NOT SET",
            "LIVEKIT_API_SECRET": "SET" if settings.LIVEKIT_API_SECRET else "NOT SET",
            "LIVEKIT_URL": settings.LIVEKIT_URL or "NOT SET"
        }
        
        print("✅ Configuration Status:")
        for key, value in config_status.items():
            status_icon = "✅" if value not in [False, "NOT SET", None] else "⚠️"
            print(f"   {status_icon} {key}: {value}")
        
        # Check critical configurations
        critical_missing = []
        if not settings.AI_VOICE_ENABLED:
            critical_missing.append("AI_VOICE_ENABLED")
        
        if critical_missing:
            print(f"❌ Critical configurations missing: {', '.join(critical_missing)}")
            return False
        else:
            print("✅ All critical voice configurations are enabled")
            return True
            
    except Exception as e:
        print(f"❌ Configuration validation error: {e}")
        return False


async def main():
    """Run all voice integration tests."""
    print("🎤 AI Agent Voice Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("Voice Agent Initialization", test_voice_agent_initialization),
        ("LiveKit Token Generation", test_livekit_token_generation),
        ("Voice Session Setup", test_voice_session_setup),
        ("Voice Processing Simulation", test_voice_processing_simulation),
        ("Configuration Validation", test_configuration_validation),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("🎤 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All voice integration tests passed!")
        return True
    else:
        print("⚠️  Some voice integration tests failed. Check configuration and dependencies.")
        return False


if __name__ == "__main__":
    asyncio.run(main())