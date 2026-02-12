"""SSE (Server-Sent Events) endpoints."""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.chat_session import ChatSession
from app.redis_client import get_redis
from app.core.sse_manager import get_sse_manager, SSEManager
from app.schemas.event import SSEEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/my/chat", tags=["sse"])


async def event_stream_generator(
    session_id: UUID,
    user_id: UUID,
    sse_manager: SSEManager,
    queue: asyncio.Queue,
):
    """
    Generator for SSE event stream.
    
    Yields events from the queue until connection is closed.
    """
    try:
        while True:
            try:
                # Wait for event with timeout to allow periodic checks
                event = await asyncio.wait_for(queue.get(), timeout=1.0)

                # None signals connection close
                if event is None:
                    logger.info(f"Connection close signal received for session {session_id}")
                    break

                # Handle heartbeat (string)
                if isinstance(event, str):
                    yield event
                    continue

                # Handle SSEEvent
                if isinstance(event, SSEEvent):
                    yield event.to_sse_format()
                    continue

                logger.warning(f"Unknown event type: {type(event)}")

            except asyncio.TimeoutError:
                # Timeout is normal, continue waiting
                continue

            except asyncio.CancelledError:
                logger.info(f"Event stream cancelled for session {session_id}")
                break

            except Exception as e:
                logger.error(f"Error in event stream: {e}")
                # Send error event to client
                error_event = SSEEvent(
                    event_type="error",
                    payload={"error": str(e)},
                    session_id=session_id,
                )
                yield error_event.to_sse_format()
                break

    finally:
        # Cleanup: unregister connection
        try:
            await sse_manager.unregister_connection(session_id, user_id, queue)
        except Exception as e:
            logger.error(f"Error unregistering connection: {e}")


@router.get(
    "/{session_id}/events/",
    response_class=StreamingResponse,
    summary="Subscribe to SSE events for a chat session",
    description="""
    Establishes a Server-Sent Events (SSE) connection to receive real-time updates
    for a specific chat session.
    
    **Event Types:**
    - `direct_agent_call` - Direct agent invocation
    - `agent_status_changed` - Agent status update
    - `task_plan_created` - Task plan created by orchestrator
    - `task_started` - Task execution started
    - `task_progress` - Task progress update
    - `task_completed` - Task completed
    - `tool_request` - Tool approval request
    - `plan_request` - Plan approval request
    - `context_retrieved` - RAG context retrieved
    - `approval_required` - User approval required
    
    **Connection Management:**
    - Heartbeat sent every 30 seconds
    - Automatic reconnection supported
    - Buffered events (last 100) sent on reconnect
    - Connection timeout: 5 minutes of inactivity
    
    **Multiple Connections:**
    - Multiple connections per session supported (e.g., multiple browser tabs)
    - Events broadcasted to all active connections
    
    **Security:**
    - User isolation enforced via JWT
    - Only events for user's own sessions are sent
    """,
)
async def subscribe_to_events(
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Subscribe to SSE events for a chat session.
    
    Args:
        session_id: Chat session UUID
        request: FastAPI request object (contains user context)
        db: Database session
        
    Returns:
        StreamingResponse with SSE events
        
    Raises:
        HTTPException: 404 if session not found, 403 if access denied
    """
    # Get user_id from request state (set by UserIsolationMiddleware)
    user_id: UUID = request.state.user_id

    # Verify session exists and belongs to user
    result = await db.execute(
        ChatSession.__table__.select().where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    session = result.first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Chat session {session_id} not found or access denied",
        )

    # Get SSE manager
    redis = await get_redis()
    sse_manager = await get_sse_manager(redis)

    # Register connection and get queue
    queue = await sse_manager.register_connection(session_id, user_id)

    logger.info(
        f"SSE connection established: user={user_id}, session={session_id}"
    )

    # Create streaming response
    return StreamingResponse(
        event_stream_generator(session_id, user_id, sse_manager, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get(
    "/stats/",
    summary="Get SSE connection statistics",
    description="""
    Returns statistics about active SSE connections.
    
    **Metrics:**
    - Total active connections
    - Total active sessions
    - Total active users
    - Connections per session breakdown
    
    **Use Cases:**
    - Monitoring dashboard
    - Debugging connection issues
    - Capacity planning
    """,
)
async def get_sse_stats(
    request: Request,
) -> dict:
    """
    Get SSE connection statistics.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dictionary with SSE statistics
    """
    # Get SSE manager
    redis = await get_redis()
    sse_manager = await get_sse_manager(redis)

    # Get stats
    stats = await sse_manager.get_stats()

    return {
        "status": "ok",
        "stats": stats,
    }
