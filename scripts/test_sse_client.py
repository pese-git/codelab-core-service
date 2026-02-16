#!/usr/bin/env python3
"""
Test Streaming client for debugging (NDJSON format).

This script connects to the streaming endpoint and prints all received events.
"""

import asyncio
import json
import sys
from uuid import UUID

import httpx


async def listen_to_stream(base_url: str, session_id: str, token: str):
    """
    Connect to streaming endpoint and listen for events (NDJSON format).
    
    Args:
        base_url: Base URL of the API (e.g., http://localhost:8000)
        session_id: Chat session UUID
        token: JWT authentication token
    """
    url = f"{base_url}/my/chat/{session_id}/events/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/x-ndjson",
    }
    
    print(f"🔌 Connecting to streaming endpoint: {url}")
    print(f"📋 Session ID: {session_id}")
    print("-" * 80)
    
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url, headers=headers) as response:
                if response.status_code != 200:
                    print(f"❌ Error: HTTP {response.status_code}")
                    print(await response.aread())
                    return
                
                print(f"✅ Connected! Listening for events (NDJSON format)...")
                print("-" * 80)
                
                async for line in response.aiter_lines():
                    line = line.strip()
                    
                    # Skip empty lines
                    if not line:
                        continue
                    
                    # Parse NDJSON format (each line is a complete JSON object)
                    try:
                        event = json.loads(line)
                        event_type = event.get('event_type', 'unknown')
                        
                        # Handle heartbeat
                        if event_type == 'heartbeat':
                            print("💓 Heartbeat")
                            continue
                        
                        # Display event
                        print(f"\n📨 Event: {event_type}")
                        print(f"   Timestamp: {event.get('timestamp', 'N/A')}")
                        print(f"   Session ID: {event.get('session_id', 'N/A')}")
                        print(f"   Payload: {json.dumps(event.get('payload', {}), indent=2)}")
                        print("-" * 80)
                        
                    except json.JSONDecodeError as e:
                        print(f"⚠️  Failed to parse JSON: {e}")
                        print(f"   Raw line: {line}")
                        
    except httpx.ConnectError as e:
        print(f"❌ Connection error: {e}")
        print(f"   Make sure the server is running at {base_url}")
    except KeyboardInterrupt:
        print("\n\n👋 Disconnected by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


async def send_test_message(base_url: str, session_id: str, token: str, agent_name: str, message: str):
    """
    Send a test message to trigger streaming events.
    
    Args:
        base_url: Base URL of the API
        session_id: Chat session UUID
        token: JWT authentication token
        agent_name: Target agent name
        message: Message content
    """
    url = f"{base_url}/my/chat/{session_id}/message/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "content": message,
        "target_agent": agent_name,
    }
    
    print(f"\n📤 Sending test message to agent '{agent_name}'...")
    print(f"   Message: {message}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Message sent successfully!")
                print(f"   Response: {data.get('content', 'N/A')[:100]}...")
            else:
                print(f"❌ Error: HTTP {response.status_code}")
                print(f"   {response.text}")
                
    except Exception as e:
        print(f"❌ Failed to send message: {e}")


async def main():
    """Main entry point."""
    if len(sys.argv) < 4:
        print("Usage: python test_sse_client.py <session_id> <token> <base_url> [send_message]")
        print()
        print("Examples:")
        print("  # Listen to SSE events:")
        print("  python test_sse_client.py 550e8400-e29b-41d4-a716-446655440000 eyJhbG... http://localhost:8000")
        print()
        print("  # Send test message and listen:")
        print("  python test_sse_client.py 550e8400-e29b-41d4-a716-446655440000 eyJhbG... http://localhost:8000 send")
        print()
        print("To get a token, use: python scripts/generate_test_jwt.py")
        sys.exit(1)
    
    session_id = sys.argv[1]
    token = sys.argv[2]
    base_url = sys.argv[3].rstrip("/")
    send_message = len(sys.argv) > 4 and sys.argv[4] == "send"
    
    # Validate session_id is UUID
    try:
        UUID(session_id)
    except ValueError:
        print(f"❌ Invalid session_id: {session_id}")
        print("   Session ID must be a valid UUID")
        sys.exit(1)
    
    if send_message:
        # Send test message in background
        asyncio.create_task(
            send_test_message(
                base_url=base_url,
                session_id=session_id,
                token=token,
                agent_name="test-agent",  # Change to your agent name
                message="Hello! This is a test message to trigger streaming events.",
            )
        )
        # Wait a bit before starting streaming listener
        await asyncio.sleep(1)
    
    # Listen to streaming events
    await listen_to_stream(base_url, session_id, token)


if __name__ == "__main__":
    asyncio.run(main())
