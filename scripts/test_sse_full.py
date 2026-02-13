#!/usr/bin/env python3
"""
Full Streaming test: creates session, agent, and tests Streaming events.
"""

import asyncio
import json
import sys

import httpx


BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjYTVlNmY4Ny1mOGMxLTRjODQtYTU4Ni05Mjk3OTc4ZDY0MmEiLCJpYXQiOjE3NzEwMDY5MjksImV4cCI6MTc3MTAwODcyOX0.XksUrF837woAw411YQa0R2-Uc1MgMnKIenRYrLE_42c"


async def ensure_user_exists(client: httpx.AsyncClient) -> bool:
    """Ensure test user exists in database."""
    print("👤 Checking if user exists...")
    
    # Try to create session - if user doesn't exist, we'll get 500
    # This is a workaround since we don't have a direct user creation endpoint
    response = await client.get(
        f"{BASE_URL}/my/agents/",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    
    if response.status_code == 500:
        print("⚠️  User doesn't exist, need to initialize database...")
        print("   Run: docker compose exec app uv run python scripts/init_db.py")
        return False
    
    print("✅ User exists")
    return True


async def create_session(client: httpx.AsyncClient) -> str:
    """Create a new chat session."""
    print("📝 Creating chat session...")
    response = await client.post(
        f"{BASE_URL}/my/chat/sessions/",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    
    if response.status_code != 201:
        print(f"❌ Failed to create session: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    data = response.json()
    session_id = data["id"]
    print(f"✅ Session created: {session_id}")
    return session_id


async def get_or_create_agent(client: httpx.AsyncClient) -> str:
    """Get existing agent or create a test agent."""
    print("\n🤖 Checking for agents...")
    
    # List agents
    response = await client.get(
        f"{BASE_URL}/my/agents/",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to list agents: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    agents = response.json()["agents"]
    
    if agents:
        agent_name = agents[0]["name"]
        print(f"✅ Using existing agent: {agent_name}")
        return agent_name
    
    # Create test agent
    print("📝 Creating test agent...")
    response = await client.post(
        f"{BASE_URL}/my/agents/",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={
            "name": "test-stream-agent",
            "description": "Test agent for Streaming",
            "system_prompt": "You are a helpful assistant. Keep responses brief.",
            "config": {
                "model": "openrouter/openai/gpt-4.1",
                "temperature": 0.7,
            },
        },
    )
    
    if response.status_code != 201:
        print(f"❌ Failed to create agent: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    agent_name = response.json()["name"]
    print(f"✅ Agent created: {agent_name}")
    return agent_name


async def listen_to_stream(session_id: str, stop_event: asyncio.Event):
    """Listen to Streaming events."""
    url = f"{BASE_URL}/my/chat/{session_id}/events/"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/x-ndjson",
    }
    
    print(f"\n🔌 Connecting to Streaming endpoint...")
    print(f"   URL: {url}")
    print("-" * 80)
    
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url, headers=headers) as response:
                if response.status_code != 200:
                    print(f"❌ Streaming connection failed: HTTP {response.status_code}")
                    print(await response.aread())
                    return
                
                print(f"✅ Streaming Connected! Listening for events (NDJSON format)...\n")
                
                event_count = 0
                
                async for line in response.aiter_lines():
                    if stop_event.is_set():
                        print("\n👋 Stopping Streaming listener...")
                        break
                    
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
                        
                        event_count += 1
                        
                        print(f"📨 Event #{event_count}: {event_type}")
                        print(f"   Timestamp: {event.get('timestamp', 'N/A')}")
                        print(f"   Session ID: {event.get('session_id', 'N/A')}")
                        
                        payload = event.get('payload', {})
                        if 'agent_name' in payload:
                            print(f"   Agent: {payload['agent_name']}")
                        if 'status' in payload:
                            print(f"   Status: {payload['status']}")
                        if 'message' in payload:
                            print(f"   Message: {payload['message'][:100]}...")
                        if 'response_preview' in payload:
                            print(f"   Response: {payload['response_preview'][:100]}...")
                        if 'error' in payload:
                            print(f"   ❌ Error: {payload['error']}")
                        
                        print()
                        
                    except json.JSONDecodeError as e:
                        print(f"⚠️  Failed to parse JSON: {e}")
                        print(f"   Raw line: {line}")
                
                print(f"\n📊 Total events received: {event_count}")
                        
    except Exception as e:
        print(f"❌ Streaming error: {e}")
        import traceback
        traceback.print_exc()


async def send_message(client: httpx.AsyncClient, session_id: str, agent_name: str):
    """Send a test message."""
    print(f"\n📤 Sending test message to agent '{agent_name}'...")
    
    response = await client.post(
        f"{BASE_URL}/my/chat/{session_id}/message/",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={
            "content": "Hello! Please tell me a short joke about programming.",
            "target_agent": agent_name,
        },
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to send message: {response.status_code}")
        print(response.text)
        return False
    
    data = response.json()
    print(f"✅ Message sent successfully!")
    print(f"   Response: {data['content'][:200]}...")
    return True


async def main():
    """Main test flow."""
    print("=" * 80)
    print("🧪 Streaming FULL TEST")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 0: Ensure user exists
        if not await ensure_user_exists(client):
            print("\n❌ User doesn't exist. Please run database initialization first:")
            print("   docker compose exec app uv run python scripts/init_db.py")
            sys.exit(1)
        
        # Step 1: Create session
        session_id = await create_session(client)
        
        # Step 2: Get or create agent
        agent_name = await get_or_create_agent(client)
        
        # Step 3: Start Streaming listener in background
        stop_event = asyncio.Event()
        stream_task = asyncio.create_task(listen_to_stream(session_id, stop_event))
        
        # Wait for Streaming to connect
        await asyncio.sleep(2)
        
        # Step 4: Send test message (should trigger Streaming events)
        success = await send_message(client, session_id, agent_name)
        
        if success:
            # Wait for events to be received
            print("\n⏳ Waiting for Streaming events (10 seconds)...")
            await asyncio.sleep(10)
        
        # Step 5: Stop Streaming listener
        stop_event.set()
        await stream_task
    
    print("\n" + "=" * 80)
    print("✅ Test completed!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Test interrupted by user")
