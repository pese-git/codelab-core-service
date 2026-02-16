"""Stream Manager for managing streaming connections."""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.schemas.event import StreamEvent, StreamEventType

logger = logging.getLogger(__name__)


class StreamConnection:
    """Represents a single streaming connection."""

    def __init__(self, session_id: UUID, user_id: UUID, queue: asyncio.Queue):
        self.session_id = session_id
        self.user_id = user_id
        self.queue = queue
        self.connected_at = datetime.now(timezone.utc)
        self.last_heartbeat = datetime.now(timezone.utc)

    async def send_event(self, event: StreamEvent) -> bool:
        """Send event to this connection."""
        try:
            await self.queue.put(event)
            return True
        except Exception as e:
            logger.error(f"Failed to send event to connection: {e}")
            return False

    async def send_heartbeat(self) -> bool:
        """Send heartbeat event."""
        try:
            heartbeat_event = StreamEvent(
                event_type=StreamEventType.HEARTBEAT,
                payload={"timestamp": datetime.now(timezone.utc).isoformat()},
                session_id=self.session_id,
            )
            await self.queue.put(heartbeat_event)
            self.last_heartbeat = datetime.now(timezone.utc)
            return True
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
            return False


class StreamManager:
    """Manager for streaming connections and event broadcasting."""

    # Constants
    MAX_BUFFER_SIZE = 100
    BUFFER_TTL = 300  # 5 minutes
    HEARTBEAT_INTERVAL = 30  # 30 seconds
    CONNECTION_TIMEOUT = 300  # 5 minutes
    MAX_EVENT_SIZE = 10240  # 10KB

    def __init__(self, redis: Redis):
        self.redis = redis
        # connections[session_id] = [StreamConnection, ...]
        self.connections: dict[UUID, list[StreamConnection]] = defaultdict(list)
        # user_sessions[user_id] = {session_id, ...}
        self.user_sessions: dict[UUID, set[UUID]] = defaultdict(set)
        self._heartbeat_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start Stream manager background tasks."""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("Stream Manager started")

    async def stop(self) -> None:
        """Stop Stream manager and close all connections."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        # Close all connections
        async with self._lock:
            for session_id, conns in self.connections.items():
                for conn in conns:
                    try:
                        await conn.queue.put(None)  # Signal to close
                    except Exception:
                        pass
            self.connections.clear()
            self.user_sessions.clear()

        logger.info("Stream Manager stopped")

    async def register_connection(
        self, session_id: UUID, user_id: UUID, since: datetime | None = None
    ) -> asyncio.Queue:
        """Register new streaming connection."""
        queue = asyncio.Queue(maxsize=1000)
        connection = StreamConnection(session_id, user_id, queue)

        async with self._lock:
            self.connections[session_id].append(connection)
            self.user_sessions[user_id].add(session_id)

        logger.info(
            f"Streaming connection registered: user={user_id}, session={session_id}, "
            f"total_connections={len(self.connections[session_id])}"
        )

        # Send buffered events if any (filtered by timestamp if provided)
        await self._send_buffered_events(session_id, connection, since)

        return queue

    async def unregister_connection(
        self, session_id: UUID, user_id: UUID, queue: asyncio.Queue
    ) -> None:
        """Unregister streaming connection."""
        async with self._lock:
            if session_id in self.connections:
                # Remove connection with matching queue
                self.connections[session_id] = [
                    conn
                    for conn in self.connections[session_id]
                    if conn.queue != queue
                ]

                # Clean up empty session
                if not self.connections[session_id]:
                    del self.connections[session_id]
                    if user_id in self.user_sessions:
                        self.user_sessions[user_id].discard(session_id)
                        if not self.user_sessions[user_id]:
                            del self.user_sessions[user_id]

        logger.info(
            f"Streaming connection unregistered: user={user_id}, session={session_id}"
        )

    async def broadcast_event(
        self, session_id: UUID, event: StreamEvent, buffer: bool = True
    ) -> int:
        """
        Broadcast event to all connections of a session.
        
        Args:
            session_id: Session UUID
            event: Event to broadcast
            buffer: Whether to buffer event in Redis
            
        Returns:
            Number of connections that received the event
        """
        # Validate event size
        event_json = event.model_dump_json()
        if len(event_json) > self.MAX_EVENT_SIZE:
            logger.warning(
                f"Event size {len(event_json)} exceeds max size {self.MAX_EVENT_SIZE}, "
                "truncating payload"
            )
            event.payload = {"error": "Payload too large, fetch via API"}

        # Buffer event in Redis if requested
        if buffer:
            await self._buffer_event(session_id, event)

        # Broadcast to all connections
        sent_count = 0
        async with self._lock:
            connections = self.connections.get(session_id, [])

        for conn in connections:
            if await conn.send_event(event):
                sent_count += 1

        logger.debug(
            f"Event broadcasted: session={session_id}, type={event.event_type}, "
            f"sent_to={sent_count}/{len(connections)}"
        )

        return sent_count

    async def broadcast_to_user(
        self, user_id: UUID, event: StreamEvent, buffer: bool = True
    ) -> int:
        """
        Broadcast event to all sessions of a user.
        
        Returns:
            Total number of connections that received the event
        """
        total_sent = 0
        async with self._lock:
            session_ids = list(self.user_sessions.get(user_id, set()))

        for session_id in session_ids:
            sent = await self.broadcast_event(session_id, event, buffer)
            total_sent += sent

        return total_sent

    async def close_session(self, session_id: UUID) -> None:
        """Close all connections for a session."""
        async with self._lock:
            connections = self.connections.get(session_id, [])

        # Send close event
        close_event = StreamEvent(
            event_type=StreamEventType.TASK_COMPLETED,
            payload={"message": "Session closed"},
            session_id=session_id,
        )

        for conn in connections:
            await conn.send_event(close_event)
            await conn.queue.put(None)  # Signal to close

        # Remove connections
        async with self._lock:
            if session_id in self.connections:
                del self.connections[session_id]

        logger.info(f"Session closed: session={session_id}")

    async def get_stats(self) -> dict[str, Any]:
        """Get Stream manager statistics."""
        async with self._lock:
            total_connections = sum(
                len(conns) for conns in self.connections.values()
            )
            total_sessions = len(self.connections)
            total_users = len(self.user_sessions)

            connections_per_session = {
                str(session_id): len(conns)
                for session_id, conns in self.connections.items()
            }

        return {
            "total_connections": total_connections,
            "total_sessions": total_sessions,
            "total_users": total_users,
            "connections_per_session": connections_per_session,
        }

    async def _buffer_event(self, session_id: UUID, event: StreamEvent) -> None:
        """Buffer event in Redis for reconnection recovery."""
        try:
            buffer_key = f"stream:buffer:{session_id}"
            event_json = event.model_dump_json()

            # Add to list (left push for FIFO)
            await self.redis.lpush(buffer_key, event_json)

            # Trim to max size
            await self.redis.ltrim(buffer_key, 0, self.MAX_BUFFER_SIZE - 1)

            # Set TTL
            await self.redis.expire(buffer_key, self.BUFFER_TTL)

        except Exception as e:
            logger.error(f"Failed to buffer event: {e}")

    async def _send_buffered_events(
        self, session_id: UUID, connection: StreamConnection, since: datetime | None = None
    ) -> None:
        """Send buffered events to a newly connected client."""
        try:
            buffer_key = f"stream:buffer:{session_id}"

            # Get all buffered events (in reverse order for FIFO)
            buffered = await self.redis.lrange(buffer_key, 0, -1)

            if buffered:
                events_to_send = []
                
                # Filter events by timestamp if 'since' is provided
                for event_json in reversed(buffered):
                    try:
                        event_data = json.loads(event_json)
                        event = StreamEvent(**event_data)
                        
                        # Only send events after 'since' timestamp
                        if since is None or event.timestamp > since:
                            events_to_send.append(event)
                    except Exception as e:
                        logger.error(f"Failed to parse buffered event: {e}")
                
                if events_to_send:
                    logger.info(
                        f"Sending {len(events_to_send)} buffered events to new connection "
                        f"(filtered from {len(buffered)} total, since={since})"
                    )
                    
                    # Send filtered events
                    for event in events_to_send:
                        try:
                            await connection.send_event(event)
                        except Exception as e:
                            logger.error(f"Failed to send buffered event: {e}")
                else:
                    logger.info(
                        f"No buffered events to send (all filtered out by since={since})"
                    )

        except Exception as e:
            logger.error(f"Failed to retrieve buffered events: {e}")

    async def _heartbeat_loop(self) -> None:
        """Background task to send heartbeats to all connections."""
        while True:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)

                async with self._lock:
                    all_connections = [
                        conn
                        for conns in self.connections.values()
                        for conn in conns
                    ]

                # Send heartbeats
                for conn in all_connections:
                    try:
                        await conn.send_heartbeat()
                    except Exception as e:
                        logger.error(f"Heartbeat failed: {e}")

                logger.debug(f"Heartbeat sent to {len(all_connections)} connections")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")


# Global Stream manager instance
_stream_manager: StreamManager | None = None


async def get_stream_manager(redis: Redis) -> StreamManager:
    """Get or create Stream manager instance."""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager(redis)
        await _stream_manager.start()
    return _stream_manager


async def close_stream_manager() -> None:
    """Close Stream manager."""
    global _stream_manager
    if _stream_manager is not None:
        await _stream_manager.stop()
        _stream_manager = None


# Backward compatibility aliases
SSEManager = StreamManager
get_sse_manager = get_stream_manager
close_sse_manager = close_stream_manager
