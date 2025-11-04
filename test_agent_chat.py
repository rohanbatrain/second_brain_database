#!/usr/bin/env python3
"""
Test LangGraph Agent Chat - Verify inference is working
"""

import requests
import json
import time
import sys

API_BASE = "http://localhost:2024"

def test_agent_chat():
    """Test the agent with a simple message"""
    
    print("=" * 80)
    print("TESTING SECOND BRAIN AGENT")
    print("=" * 80)
    
    # Step 1: Create a thread
    print("\n1. Creating thread...")
    response = requests.post(f"{API_BASE}/threads", json={})
    
    if response.status_code != 200:
        print(f"❌ Failed to create thread: {response.status_code}")
        print(response.text)
        return False
    
    thread_data = response.json()
    thread_id = thread_data["thread_id"]
    print(f"✓ Thread created: {thread_id}")
    
    # Step 2: Send a message
    print("\n2. Sending message to agent...")
    test_message = "Hello! Can you introduce yourself as Second Brain Agent?"
    
    run_payload = {
        "assistant_id": "agent",
        "input": {
            "messages": [{"role": "user", "content": test_message}]
        },
        "stream_mode": ["values"]
    }
    
    response = requests.post(
        f"{API_BASE}/threads/{thread_id}/runs",
        json=run_payload
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to create run: {response.status_code}")
        print(response.text)
        return False
    
    run_data = response.json()
    run_id = run_data["run_id"]
    print(f"✓ Run created: {run_id}")
    print(f"  Status: {run_data['status']}")
    
    # Step 3: Wait for completion and get response
    print("\n3. Waiting for agent response...")
    max_attempts = 30
    attempt = 0
    
    while attempt < max_attempts:
        time.sleep(1)
        attempt += 1
        
        # Check run status
        response = requests.get(f"{API_BASE}/threads/{thread_id}/runs/{run_id}")
        
        if response.status_code != 200:
            print(f"❌ Failed to get run status: {response.status_code}")
            return False
        
        run_status = response.json()
        status = run_status["status"]
        
        print(f"  [{attempt}] Status: {status}")
        
        if status == "success":
            print("\n✓ Run completed successfully!")
            
            # Get the thread state to see messages
            response = requests.get(f"{API_BASE}/threads/{thread_id}/state")
            
            if response.status_code == 200:
                state = response.json()
                messages = state.get("values", {}).get("messages", [])
                
                print(f"\n4. CONVERSATION:")
                print("-" * 80)
                
                for msg in messages:
                    role = msg.get("type", "unknown")
                    content = msg.get("content", "")
                    
                    if role == "human":
                        print(f"\n👤 USER:\n{content}")
                    elif role == "ai":
                        print(f"\n🤖 AGENT:\n{content}")
                    elif role == "tool":
                        tool_name = msg.get("name", "unknown")
                        print(f"\n🔧 TOOL ({tool_name}):")
                        print(f"{content[:200]}..." if len(content) > 200 else content)
                
                print("\n" + "-" * 80)
                print("\n✅ AGENT IS WORKING! Inference successful!")
                return True
            else:
                print(f"⚠️  Could not retrieve messages: {response.status_code}")
                return True  # Run succeeded even if we can't get messages
        
        elif status == "error":
            print(f"\n❌ Run failed with error")
            print(json.dumps(run_status, indent=2))
            return False
        
        elif status == "pending" or status == "running":
            # Still processing, continue waiting
            continue
        
        else:
            print(f"\n⚠️  Unexpected status: {status}")
    
    print(f"\n❌ Timeout waiting for response (tried {max_attempts} times)")
    return False

if __name__ == "__main__":
    try:
        success = test_agent_chat()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
