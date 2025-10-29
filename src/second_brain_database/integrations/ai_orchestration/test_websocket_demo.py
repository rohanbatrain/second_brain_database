"""
WebSocket Communication Demo

This script demonstrates the real-time WebSocket communication capabilities
of the AI orchestration system.
"""

import asyncio
import json
from datetime import datetime, timezone

from second_brain_database.integrations.ai_orchestration.event_bus import get_ai_event_bus
from second_brain_database.integrations.ai_orchestration.models.events import AIEvent, EventType
from second_brain_database.integrations.ai_orchestration.models.session import (
    SessionContext,
    ConversationMessage,
    MessageRole,
    AgentType,
    SessionStatus
)


async def demo_websocket_communication():
    """
    Demonstrate real-time WebSocket communication with AI agents.
    """
    print("🚀 Starting AI WebSocket Communication Demo")
    print("=" * 50)
    
    # Initialize event bus
    event_bus = get_ai_event_bus()
    print(f"✅ Event bus initialized: {event_bus.get_session_stats()}")
    
    # Create a demo session
    session_id = "demo-session-123"
    user_id = "demo-user-456"
    
    session_context = SessionContext(
        session_id=session_id,
        user_id=user_id,
        agent_type=AgentType.PERSONAL,
        status=SessionStatus.ACTIVE,
        voice_enabled=False
    )
    
    print(f"✅ Created demo session: {session_id}")
    
    # Simulate various AI events
    events_to_demo = [
        # Session start
        AIEvent.create_status_event(
            session_id, "personal", EventType.SESSION_START,
            "AI session started with personal agent"
        ),
        
        # User message received
        AIEvent(
            type=EventType.THINKING,
            data={"status": "thinking", "message": "Processing your message..."},
            session_id=session_id,
            agent_type="personal"
        ),
        
        # Tool call
        AIEvent.create_tool_call_event(
            session_id, "personal", "get_user_profile",
            {"user_id": user_id, "include_preferences": True}
        ),
        
        # Tool result
        AIEvent.create_tool_result_event(
            session_id, "personal", "get_user_profile",
            {"username": "demo_user", "preferences": {"theme": "dark", "language": "en"}}
        ),
        
        # Typing status
        AIEvent.create_status_event(
            session_id, "personal", EventType.TYPING,
            "Generating response..."
        ),
        
        # Token streaming (simulating real-time response)
        *[AIEvent.create_token_event(session_id, "personal", token)
          for token in ["Hello", " there!", " I", " can", " see", " your", " preferences", " are", " set", " to", " dark", " theme.", " How", " can", " I", " help", " you", " today?"]],
        
        # Complete response
        AIEvent.create_response_event(
            session_id, "personal",
            "Hello there! I can see your preferences are set to dark theme. How can I help you today?"
        ),
        
        # Agent switch demonstration
        AIEvent.create_status_event(
            session_id, "family", EventType.AGENT_SWITCH,
            "Switched to family agent for family management tasks"
        ),
        
        # Family tool call
        AIEvent.create_tool_call_event(
            session_id, "family", "list_family_members",
            {"family_id": "family-789"}
        ),
        
        # TTS audio (simulated)
        AIEvent.create_tts_event(
            session_id, "family", "base64_audio_data_here",
            {"duration": 2.5, "format": "wav"}
        ),
        
        # Error handling
        AIEvent.create_error_event(
            session_id, "commerce", "Payment processing failed",
            "PAYMENT_DECLINED", {"retry_after": 300}
        ),
        
        # Session end
        AIEvent.create_status_event(
            session_id, "personal", EventType.SESSION_END,
            "AI session completed successfully"
        )
    ]
    
    print(f"\n📡 Simulating {len(events_to_demo)} WebSocket events:")
    print("-" * 50)
    
    # Simulate event streaming
    for i, event in enumerate(events_to_demo, 1):
        # Convert to WebSocket message format
        websocket_message = event.to_websocket_message()
        
        # Pretty print the event
        print(f"\n[{i:2d}] Event Type: {event.type.upper()}")
        print(f"     Agent: {event.agent_type}")
        print(f"     Data: {json.dumps(event.data, indent=6)}")
        
        if event.tool_name:
            print(f"     Tool: {event.tool_name}")
        
        if event.error_code:
            print(f"     Error Code: {event.error_code}")
        
        print(f"     WebSocket Message Size: {len(json.dumps(websocket_message))} bytes")
        
        # Simulate real-time streaming delay
        if event.type == EventType.TOKEN:
            await asyncio.sleep(0.1)  # Fast token streaming
        else:
            await asyncio.sleep(0.3)  # Normal event delay
    
    print("\n" + "=" * 50)
    print("🎉 WebSocket Communication Demo Complete!")
    print("\nKey Features Demonstrated:")
    print("✅ Real-time token streaming")
    print("✅ Tool execution tracking")
    print("✅ Status updates (thinking, typing, etc.)")
    print("✅ Agent switching capabilities")
    print("✅ Error handling and reporting")
    print("✅ Multi-modal events (text, voice)")
    print("✅ Structured WebSocket message format")
    print("✅ Event metadata and timestamps")
    
    # Show final event bus stats
    final_stats = event_bus.get_session_stats()
    print(f"\n📊 Final Event Bus Stats: {final_stats}")


if __name__ == "__main__":
    asyncio.run(demo_websocket_communication())