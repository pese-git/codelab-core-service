"""Test script to verify MESSAGE_CREATED events are sent correctly."""

import asyncio
import json
import sys
from datetime import datetime
from uuid import uuid4

import httpx


async def test_message_events():
    """Test that MESSAGE_CREATED events are sent for both user and assistant messages."""
    
    # Configuration
    BASE_URL = "http://localhost:8000"
    TOKEN = "test-token-user1"  # Use test token from generate_test_jwt.py
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    
    print("🧪 Testing MESSAGE_CREATED events\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Create a chat session
        print("1️⃣ Creating chat session...")
        response = await client.post(
            f"{BASE_URL}/my/chat/sessions/",
            headers=headers,
        )
        
        if response.status_code != 201:
            print(f"❌ Failed to create session: {response.status_code}")
            print(response.text)
            return
        
        session_data = response.json()
        session_id = session_data["id"]
        print(f"✅ Session created: {session_id}\n")
        
        # Step 2: Connect to streaming endpoint
        print("2️⃣ Connecting to streaming endpoint...")
        
        events_received = []
        
        async def stream_listener():
            """Listen to streaming events."""
            async with client.stream(
                "GET",
                f"{BASE_URL}/my/chat/{session_id}/events/",
                headers=headers,
            ) as response:
                if response.status_code != 200:
                    print(f"❌ Failed to connect to stream: {response.status_code}")
                    return
                
                print("✅ Connected to stream\n")
                
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            event = json.loads(line)
                            events_received.append(event)
                            
                            event_type = event.get("event_type")
                            timestamp = event.get("timestamp")
                            payload = event.get("payload", {})
                            
                            print(f"📨 Event: {event_type}")
                            print(f"   Timestamp: {timestamp}")
                            
                            if event_type == "message_created":
                                print(f"   ✨ MESSAGE_CREATED event:")
                                print(f"      - message_id: {payload.get('message_id')}")
                                print(f"      - role: {payload.get('role')}")
                                print(f"      - content: {payload.get('content')[:50]}...")
                                print(f"      - agent_id: {payload.get('agent_id', 'N/A')}")
                                print(f"      - agent_name: {payload.get('agent_name', 'N/A')}")
                            elif event_type == "task_completed":
                                print(f"   ✅ Task completed")
                                # Stop listening after task completion
                                return
                            
                            print()
                            
                        except json.JSONDecodeError as e:
                            print(f"⚠️ Failed to parse event: {e}")
        
        # Start streaming listener in background
        stream_task = asyncio.create_task(stream_listener())
        
        # Wait a bit for connection to establish
        await asyncio.sleep(1)
        
        # Step 3: Send a message
        print("3️⃣ Sending message to agent...")
        message_response = await client.post(
            f"{BASE_URL}/my/chat/{session_id}/message/",
            headers=headers,
            json={
                "content": "привет",
                "target_agent": "test-agent",
            },
        )
        
        if message_response.status_code != 200:
            print(f"❌ Failed to send message: {message_response.status_code}")
            print(message_response.text)
            stream_task.cancel()
            return
        
        print(f"✅ Message sent\n")
        
        # Wait for stream to complete
        try:
            await asyncio.wait_for(stream_task, timeout=10.0)
        except asyncio.TimeoutError:
            print("⚠️ Stream timeout")
            stream_task.cancel()
        
        # Step 4: Analyze events
        print("\n" + "="*60)
        print("📊 Event Analysis")
        print("="*60)
        
        message_created_events = [
            e for e in events_received if e.get("event_type") == "message_created"
        ]
        
        print(f"\nTotal events received: {len(events_received)}")
        print(f"MESSAGE_CREATED events: {len(message_created_events)}")
        
        if len(message_created_events) >= 2:
            print("\n✅ SUCCESS: Both user and assistant messages sent as events")
            
            user_msg = next((e for e in message_created_events if e["payload"]["role"] == "user"), None)
            assistant_msg = next((e for e in message_created_events if e["payload"]["role"] == "assistant"), None)
            
            if user_msg:
                print("\n👤 User message event:")
                print(f"   - Has message_id: {'message_id' in user_msg['payload']}")
                print(f"   - Has role: {'role' in user_msg['payload']}")
                print(f"   - Has content: {'content' in user_msg['payload']}")
                print(f"   - Has timestamp: {'timestamp' in user_msg['payload']}")
            
            if assistant_msg:
                print("\n🤖 Assistant message event:")
                print(f"   - Has message_id: {'message_id' in assistant_msg['payload']}")
                print(f"   - Has role: {'role' in assistant_msg['payload']}")
                print(f"   - Has content: {'content' in assistant_msg['payload']}")
                print(f"   - Has agent_id: {'agent_id' in assistant_msg['payload']}")
                print(f"   - Has agent_name: {'agent_name' in assistant_msg['payload']}")
                print(f"   - Has timestamp: {'timestamp' in assistant_msg['payload']}")
        else:
            print(f"\n❌ FAILED: Expected 2 MESSAGE_CREATED events, got {len(message_created_events)}")
            print("\nAll events received:")
            for event in events_received:
                print(f"  - {event.get('event_type')}")


if __name__ == "__main__":
    try:
        asyncio.run(test_message_events())
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
