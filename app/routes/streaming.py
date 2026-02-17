"""Streaming endpoints for real-time events via Fetch API."""

import asyncio
import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.project_validation import get_project_with_validation
from app.middleware.user_isolation import get_current_user_id
from app.models.chat_session import ChatSession
from app.models.user_project import UserProject
from app.redis_client import get_redis
from app.core.stream_manager import get_stream_manager, StreamManager
from app.schemas.event import StreamEvent

logger = logging.getLogger(__name__)

project_router = APIRouter(prefix="/my/projects", tags=["project-streaming"])


async def event_stream_generator(
    session_id: UUID,
    user_id: UUID,
    stream_manager: StreamManager,
    queue: asyncio.Queue,
):
    """
    Generator for streaming event stream in NDJSON format.
    
    Yields events from the queue until connection is closed.
    Each event is a JSON object followed by a newline.
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

                # Handle StreamEvent
                if isinstance(event, StreamEvent):
                    yield event.to_ndjson()
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
                error_event = StreamEvent(
                    event_type="error",
                    payload={"error": str(e)},
                    session_id=session_id,
                )
                yield error_event.to_ndjson()
                break

    finally:
        # Cleanup: unregister connection
        try:
            await stream_manager.unregister_connection(session_id, user_id, queue)
        except Exception as e:
            logger.error(f"Error unregistering connection: {e}")


# Per-project streaming endpoints
@project_router.get(
    "/{project_id}/chat/{session_id}/events/",
    response_class=StreamingResponse,
    summary="Subscribe to streaming events for a chat session in project",
    description="""
    Establishes a streaming connection to receive real-time updates
    for a specific chat session in a project using Fetch API and JSON Lines (NDJSON) format.
    
    **Authentication:**
    - Requires JWT token in Authorization header: `Bearer <token>`
    - Query parameter authentication is NOT supported for security reasons
    
    **Response Format:**
    - Content-Type: `application/x-ndjson`
    - Each event is a JSON object on a separate line
    - Format: `{"event_type": "...", "payload": {...}, "timestamp": "...", "session_id": "..."}\n`
    
    **Event Types:**
    - `message_created` - New message created (user or assistant)
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
    - `heartbeat` - Keep-alive heartbeat (sent every 30 seconds)
    - `error` - Error occurred
    
    **Connection Management:**
    - Heartbeat sent every 30 seconds as JSON event
    - Connection timeout: 5 minutes of inactivity
    - Buffered events (last 100) sent on reconnect
    - Use `?since=<timestamp>` to retrieve only events after a specific time (prevents duplicates on reconnect)
    
    **Security:**
    - User isolation enforced via JWT
    - Project isolation enforced - only events for user's project sessions are sent
    """,
)
async def subscribe_to_project_events(
    project_id: UUID,
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    project: UserProject = Depends(get_project_with_validation),
    since: datetime | None = Query(
        default=None,
        description="ISO 8601 timestamp - only return buffered events after this time (prevents duplicates on reconnect)"
    ),
) -> StreamingResponse:
    """
    Subscribe to streaming events for a chat session in a project.
    
    Args:
        project_id: Project UUID
        session_id: Chat session UUID
        request: FastAPI request object (contains user context)
        db: Database session
        project: User project (validated via dependency)
        since: Optional timestamp to filter buffered events (only events after this time)
        
    Returns:
        StreamingResponse with NDJSON events
        
    Raises:
        HTTPException: 404 if session not found, 403 if access denied
    """
    # Get user_id from request
    user_id = get_current_user_id(request)
    
    logger.info(f"Verifying session access: project_id={project_id}, session_id={session_id}, user_id={user_id}")

    # Verify session exists and belongs to user and project
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.project_id == project_id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        logger.warning(f"Session not found: project_id={project_id}, session_id={session_id}, user_id={user_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Chat session {session_id} not found in project {project_id}",
        )

    # Get Stream manager
    redis = await get_redis()
    stream_manager = await get_stream_manager(redis)

    # Register connection and get queue (with optional 'since' filter)
    queue = await stream_manager.register_connection(session_id, user_id, since)

    logger.info(
        f"Streaming connection established: user={user_id}, project={project_id}, session={session_id}, since={since}"
    )

    # Create streaming response
    return StreamingResponse(
        event_stream_generator(session_id, user_id, stream_manager, queue),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
