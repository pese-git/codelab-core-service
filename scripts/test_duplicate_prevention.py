#!/usr/bin/env python3
"""
Test script to verify duplicate message prevention in streaming events.

This script tests the 'since' parameter functionality that prevents
duplicate events when reconnecting to the event stream.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

# Import token generation
from scripts.generate_test_jwt import generate_test_token


class StreamingClient:
    """Client for testing streaming events with duplicate prevention."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"}
        self.last_event_timestamp = None
        self.received_events = []

    async def create_session(self) -> str:
        """Create a new chat session."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/my/chat/sessions/",
                headers=self.headers,
            )
            response.raise_for_status()
            data = response.json()
            return data["id"]

    async def send_message(self, session_id: str, content: str, target_agent: str | None = None):
        """Send a message to the chat session."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {"content": content}
            if target_agent:
                payload["target_agent"] = target_agent
            
            response = await client.post(
                f"{self.base_url}/my/chat/{session_id}/message/",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def connect_to_stream(self, session_id: str, duration: float = 5.0):
        """
        Connect to event stream and collect events.
        
        Args:
            session_id: Chat session ID
            duration: How long to listen for events (seconds)
        """
        # Build URL with 'since' parameter if we have a last timestamp
        url = f"{self.base_url}/my/chat/{session_id}/events/"
        if self.last_event_timestamp:
            url += f"?since={self.last_event_timestamp}"
            print(f"🔄 Reconnecting with since={self.last_event_timestamp}")
        else:
            print("🆕 Initial connection (no 'since' parameter)")

        events_in_this_connection = []

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url, headers=self.headers) as response:
                response.raise_for_status()
                
                start_time = asyncio.get_event_loop().time()
                buffer = ""
                
                async for chunk in response.aiter_bytes():
                    # Check timeout
                    if asyncio.get_event_loop().time() - start_time > duration:
                        print(f"⏱️  Duration {duration}s reached, closing connection")
                        break
                    
                    # Decode chunk and add to buffer
                    buffer += chunk.decode("utf-8")
                    
                    # Process complete lines
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        
                        if not line:
                            continue
                        
                        try:
                            event = json.loads(line)
                            event_type = event.get("event_type")
                            timestamp = event.get("timestamp")
                            
                            # Skip heartbeat events for cleaner output
                            if event_type == "heartbeat":
                                continue
                            
                            # Store event
                            events_in_this_connection.append(event)
                            self.received_events.append(event)
                            
                            # Update last timestamp
                            if timestamp:
                                self.last_event_timestamp = timestamp
                            
                            # Print event info
                            payload = event.get("payload", {})
                            if event_type == "message_created":
                                role = payload.get("role", "unknown")
                                content = payload.get("content", "")[:50]
                                print(f"  📨 {event_type}: {role} - {content}... (ts: {timestamp})")
                            else:
                                print(f"  📡 {event_type}: {payload} (ts: {timestamp})")
                        
                        except json.JSONDecodeError as e:
                            print(f"  ⚠️  Failed to parse event: {e}")
                            print(f"     Line: {line[:100]}")
        
        return events_in_this_connection


async def test_duplicate_prevention():
    """Test that duplicate events are prevented on reconnection."""
    
    print("=" * 70)
    print("🧪 Testing Duplicate Event Prevention")
    print("=" * 70)
    
    # Configuration
    BASE_URL = "http://localhost:8000"
    
    # Generate valid JWT token
    print("\n🔐 Generating test JWT token...")
    TOKEN = generate_test_token(user_id="123e4567-e89b-12d3-a456-426614174000", expire_minutes=60)
    print(f"✅ Token generated (expires in 60 minutes)")
    
    client = StreamingClient(BASE_URL, TOKEN)
    
    try:
        # Step 1: Create session
        print("\n📝 Step 1: Creating chat session...")
        session_id = await client.create_session()
        print(f"✅ Session created: {session_id}")
        
        # Step 2: Connect to stream (initial connection)
        print("\n📡 Step 2: Connecting to event stream (initial)...")
        await asyncio.sleep(1)  # Give server time to set up
        
        # Start listening in background
        stream_task = asyncio.create_task(client.connect_to_stream(session_id, duration=3.0))
        
        # Wait a bit then send a message
        await asyncio.sleep(0.5)
        
        print("\n💬 Step 3: Sending first message...")
        await client.send_message(session_id, "Привет")  # No target_agent = orchestrated mode
        
        # Wait for stream to finish
        events_first_connection = await stream_task
        print(f"\n✅ First connection received {len(events_first_connection)} events")
        
        # Step 4: Reconnect (simulating page refresh or connection loss)
        print("\n🔄 Step 4: Reconnecting to stream (simulating reconnect)...")
        await asyncio.sleep(1)
        
        # Start second connection with 'since' parameter
        stream_task2 = asyncio.create_task(client.connect_to_stream(session_id, duration=3.0))
        
        # Send another message
        await asyncio.sleep(0.5)
        print("\n💬 Step 5: Sending second message...")
        await client.send_message(session_id, "Как дела?")  # No target_agent = orchestrated mode
        
        # Wait for stream to finish
        events_second_connection = await stream_task2
        print(f"\n✅ Second connection received {len(events_second_connection)} events")
        
        # Step 5: Analyze results
        print("\n" + "=" * 70)
        print("📊 Analysis")
        print("=" * 70)
        
        print(f"\nTotal events received across all connections: {len(client.received_events)}")
        print(f"Events in first connection: {len(events_first_connection)}")
        print(f"Events in second connection: {len(events_second_connection)}")
        
        # Check for duplicates by comparing event IDs or content
        event_signatures = []
        duplicates = []
        
        for event in client.received_events:
            # Create signature from event type, timestamp, and key payload fields
            sig = (
                event.get("event_type"),
                event.get("timestamp"),
                json.dumps(event.get("payload", {}), sort_keys=True)
            )
            
            if sig in event_signatures:
                duplicates.append(event)
            else:
                event_signatures.append(sig)
        
        print(f"\n🔍 Duplicate Detection:")
        if duplicates:
            print(f"  ❌ Found {len(duplicates)} duplicate events!")
            print("\n  Duplicate events:")
            for dup in duplicates:
                print(f"    - {dup.get('event_type')} at {dup.get('timestamp')}")
            print("\n  ⚠️  TEST FAILED: Duplicates detected")
            return False
        else:
            print(f"  ✅ No duplicates found!")
            print(f"  ✅ All {len(client.received_events)} events are unique")
            
            # Verify that second connection didn't receive old events
            if events_second_connection:
                first_timestamps = [e.get("timestamp") for e in events_first_connection]
                second_timestamps = [e.get("timestamp") for e in events_second_connection]
                
                # Check if any timestamp from second connection is older than last from first
                if first_timestamps and second_timestamps:
                    last_first = max(first_timestamps)
                    oldest_second = min(second_timestamps)
                    
                    if oldest_second <= last_first:
                        print(f"\n  ⚠️  Warning: Second connection received events from before last event of first connection")
                        print(f"     Last event in first connection: {last_first}")
                        print(f"     Oldest event in second connection: {oldest_second}")
                    else:
                        print(f"\n  ✅ Second connection only received new events")
                        print(f"     Last event in first connection: {last_first}")
                        print(f"     Oldest event in second connection: {oldest_second}")
            
            print("\n  ✅ TEST PASSED: No duplicates detected")
            return True
    
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main entry point."""
    print("\n🚀 Starting duplicate prevention test...\n")
    
    success = await test_duplicate_prevention()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
