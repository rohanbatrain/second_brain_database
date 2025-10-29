"""
Simple test for AI security functionality.
"""

import asyncio
from datetime import datetime, timezone

from ....integrations.mcp.context import MCPUserContext
from .ai_security_manager import ai_security_manager, AIPermission, ConversationPrivacyMode
from .privacy_manager import ai_privacy_manager
from .security_integration import ai_security_integration


async def test_security_functionality():
    """Test basic security functionality."""
    print("Testing AI Security Implementation...")
    
    # Create test user context
    user_context = MCPUserContext(
        user_id="test_user_123",
        username="test_user",
        permissions=["ai:basic_chat", "ai:voice_interaction"]
    )
    
    # Test 1: Check AI permissions
    print("\n1. Testing AI permissions...")
    try:
        await ai_security_manager.check_ai_permissions(
            user_context, AIPermission.BASIC_CHAT
        )
        print("✓ Basic chat permission check passed")
    except Exception as e:
        print(f"✗ Basic chat permission check failed: {e}")
    
    # Test 2: Log audit event
    print("\n2. Testing audit logging...")
    try:
        await ai_security_manager.log_ai_audit_event(
            user_context=user_context,
            session_id="test_session_123",
            event_type="test_event",
            agent_type="personal",
            action="test_action",
            details={"test": "data"},
            privacy_mode=ConversationPrivacyMode.PRIVATE,
            success=True
        )
        print("✓ Audit logging successful")
    except Exception as e:
        print(f"✗ Audit logging failed: {e}")
    
    # Test 3: Privacy settings
    print("\n3. Testing privacy settings...")
    try:
        privacy_settings = await ai_privacy_manager.get_user_privacy_settings(
            user_context.user_id
        )
        print(f"✓ Privacy settings retrieved: {len(privacy_settings)} settings")
    except Exception as e:
        print(f"✗ Privacy settings retrieval failed: {e}")
    
    # Test 4: Conversation privacy validation
    print("\n4. Testing conversation privacy validation...")
    try:
        is_valid = await ai_privacy_manager.validate_conversation_privacy(
            user_context.user_id,
            ConversationPrivacyMode.PRIVATE
        )
        print(f"✓ Privacy validation result: {is_valid}")
    except Exception as e:
        print(f"✗ Privacy validation failed: {e}")
    
    # Test 5: Store encrypted conversation
    print("\n5. Testing encrypted conversation storage...")
    try:
        conversation_data = {
            "messages": [
                {
                    "role": "user",
                    "content": "Hello, this is a test message",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            ]
        }
        
        stored = await ai_privacy_manager.store_conversation(
            conversation_id="test_conversation_123",
            user_context=user_context,
            conversation_data=conversation_data,
            privacy_mode=ConversationPrivacyMode.ENCRYPTED,
            agent_type="personal"
        )
        print(f"✓ Encrypted conversation storage result: {stored}")
    except Exception as e:
        print(f"✗ Encrypted conversation storage failed: {e}")
    
    # Test 6: Retrieve encrypted conversation
    print("\n6. Testing encrypted conversation retrieval...")
    try:
        retrieved = await ai_privacy_manager.retrieve_conversation(
            conversation_id="test_conversation_123",
            user_context=user_context
        )
        if retrieved:
            print("✓ Encrypted conversation retrieved successfully")
        else:
            print("✗ No conversation data retrieved")
    except Exception as e:
        print(f"✗ Encrypted conversation retrieval failed: {e}")
    
    print("\nAI Security Implementation Test Complete!")


if __name__ == "__main__":
    asyncio.run(test_security_functionality())