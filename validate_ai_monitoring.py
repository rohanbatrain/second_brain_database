#!/usr/bin/env python3
"""
Validation script for AI performance monitoring integration
Tests the optimization implementations for task 10.1
"""

import asyncio
import time
import json
from datetime import datetime
from src.second_brain_database.utils.ai_metrics import (
    ai_performance_monitor, 
    PerformanceTimer,
    performance_timer
)

async def test_message_response_time():
    """Test message response time monitoring (Requirement 8.1)"""
    print("Testing message response time monitoring...")
    
    session_id = "test_session_001"
    ai_performance_monitor.start_session(session_id)
    
    # Simulate various response times
    test_times = [0.2, 0.45, 0.6, 0.3, 0.8]  # Some above and below 500ms threshold
    
    for i, response_time in enumerate(test_times):
        ai_performance_monitor.record_message_response_time(session_id, response_time)
        print(f"  Message {i+1}: {response_time*1000:.0f}ms")
    
    # Get session metrics
    session_metrics = ai_performance_monitor.get_session_metrics(session_id)
    print(f"  Average response time: {session_metrics['avg_response_time_ms']:.1f}ms")
    
    ai_performance_monitor.end_session(session_id)
    return session_metrics['avg_response_time_ms'] < 500  # Should be under target

async def test_token_latency():
    """Test token streaming latency monitoring (Requirement 8.2)"""
    print("\nTesting token latency monitoring...")
    
    session_id = "test_session_002"
    ai_performance_monitor.start_session(session_id)
    
    # Simulate token streaming with various latencies
    test_latencies = [0.05, 0.08, 0.12, 0.06, 0.15]  # Some above and below 100ms threshold
    
    for i, latency in enumerate(test_latencies):
        ai_performance_monitor.record_token_latency(session_id, latency)
        print(f"  Token {i+1}: {latency*1000:.0f}ms")
    
    ai_performance_monitor.end_session(session_id)
    return True

async def test_voice_processing():
    """Test voice processing time monitoring (Requirement 8.3)"""
    print("\nTesting voice processing monitoring...")
    
    session_id = "test_session_003"
    ai_performance_monitor.start_session(session_id)
    
    # Simulate STT processing times
    stt_times = [1.2, 2.8, 3.5, 1.8, 4.2]  # Some above and below 3s threshold
    
    for i, processing_time in enumerate(stt_times):
        ai_performance_monitor.record_voice_processing_time(session_id, processing_time, "stt")
        print(f"  STT {i+1}: {processing_time:.1f}s")
    
    # Simulate TTS playback times
    tts_times = [0.5, 0.8, 1.2, 0.6, 1.5]  # Some above and below 1s threshold
    
    for i, processing_time in enumerate(tts_times):
        ai_performance_monitor.record_voice_processing_time(session_id, processing_time, "tts")
        print(f"  TTS {i+1}: {processing_time:.1f}s")
    
    ai_performance_monitor.end_session(session_id)
    return True

async def test_websocket_monitoring():
    """Test WebSocket connection monitoring"""
    print("\nTesting WebSocket monitoring...")
    
    session_id = "test_session_004"
    
    # Simulate WebSocket events
    events = ["connections", "messages_sent", "messages_received", "reconnections", "disconnections"]
    
    for event in events:
        ai_performance_monitor.record_websocket_event(event, session_id)
        print(f"  Recorded {event}")
    
    return True

async def test_tool_execution_monitoring():
    """Test tool execution monitoring"""
    print("\nTesting tool execution monitoring...")
    
    session_id = "test_session_005"
    ai_performance_monitor.start_session(session_id)
    
    # Simulate tool executions
    tools = [
        ("family_invite", 0.8, True),
        ("wallet_balance", 0.3, True),
        ("security_check", 1.2, False),
        ("shop_purchase", 2.1, True)
    ]
    
    for tool_name, execution_time, success in tools:
        ai_performance_monitor.record_tool_execution(session_id, tool_name, execution_time, success)
        status = "success" if success else "failed"
        print(f"  {tool_name}: {execution_time:.1f}s ({status})")
    
    ai_performance_monitor.end_session(session_id)
    return True

@performance_timer("test_operation")
async def test_performance_timer():
    """Test the performance timer decorator"""
    print("\nTesting performance timer decorator...")
    await asyncio.sleep(0.1)  # Simulate work
    print("  Timer decorator test completed")
    return True

async def test_performance_summary():
    """Test performance summary generation"""
    print("\nTesting performance summary...")
    
    summary = ai_performance_monitor.get_performance_summary()
    
    print(f"  Health Status: {summary['health_status']}")
    print(f"  Active Sessions: {summary['session_metrics']['active_sessions']}")
    print(f"  Total Messages: {summary['session_metrics']['total_messages']}")
    print(f"  WebSocket Connections: {summary['websocket_stats']['connections']}")
    
    # Validate summary structure
    required_keys = ['timestamp', 'performance_metrics', 'session_metrics', 'websocket_stats', 'health_status']
    return all(key in summary for key in required_keys)

async def main():
    """Run all validation tests"""
    print("=== AI Performance Monitoring Validation ===")
    print(f"Started at: {datetime.now().isoformat()}")
    
    tests = [
        ("Message Response Time", test_message_response_time),
        ("Token Latency", test_token_latency),
        ("Voice Processing", test_voice_processing),
        ("WebSocket Monitoring", test_websocket_monitoring),
        ("Tool Execution", test_tool_execution_monitoring),
        ("Performance Timer", test_performance_timer),
        ("Performance Summary", test_performance_summary),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results[test_name] = "PASS" if result else "FAIL"
            print(f"✓ {test_name}: {results[test_name]}")
        except Exception as e:
            results[test_name] = f"ERROR: {str(e)}"
            print(f"✗ {test_name}: {results[test_name]}")
    
    print(f"\n=== Validation Results ===")
    passed = sum(1 for result in results.values() if result == "PASS")
    total = len(results)
    
    for test_name, result in results.items():
        status_icon = "✓" if result == "PASS" else "✗"
        print(f"{status_icon} {test_name}: {result}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All AI performance monitoring tests passed!")
        return True
    else:
        print("❌ Some tests failed. Check implementation.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)