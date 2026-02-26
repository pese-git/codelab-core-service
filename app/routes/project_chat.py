"""Per-project chat endpoints."""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.manager import AgentManager
from app.core.stream_manager import get_stream_manager
from app.core.user_worker_space import UserWorkerSpace
from app.database import get_db
from app.dependencies import get_worker_space
from app.middleware.project_validation import get_project_with_validation
from app.middleware.user_isolation import get_current_user_id
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.user_project import UserProject
from app.qdrant_client import get_qdrant
from app.redis_client import get_redis
from app.schemas.chat import (
    ChatSessionListResponse,
    ChatSessionResponse,
    MessageListResponse,
    MessageRequest,
    MessageResponse,
    MessageRole,
)
from app.schemas.error import LLMProviderError
from app.schemas.event import StreamEvent, StreamEventType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/my/projects/{project_id}/chat", tags=["project-chat"])


@router.post("/sessions/", status_code=status.HTTP_201_CREATED, response_model=ChatSessionResponse)
async def create_project_session(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    project: UserProject = Depends(get_project_with_validation),
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> ChatSessionResponse:
    """Create new chat session in project."""
    user_id = get_current_user_id(request)
    logger.info(f"Creating chat session in project: project_id={project_id}, user_id={user_id}")
    
    session = ChatSession(user_id=user_id, project_id=project_id)
    db.add(session)
    await db.flush()
    
    logger.info(f"Chat session created: session_id={session.id}, project_id={project_id}")
    
    return ChatSessionResponse(
        id=session.id,
        created_at=session.created_at,
        message_count=0,
    )


@router.get("/sessions/", response_model=ChatSessionListResponse)
async def list_project_sessions(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    project: UserProject = Depends(get_project_with_validation),
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> ChatSessionListResponse:
    """List all chat sessions in project."""
    user_id = get_current_user_id(request)
    logger.info(f"Listing chat sessions in project: project_id={project_id}, user_id={user_id}")
    
    # Get sessions with message count using subquery
    stmt = (
        select(
            ChatSession.id,
            ChatSession.created_at,
            func.count(Message.id).label('message_count')
        )
        .outerjoin(Message, Message.session_id == ChatSession.id)
        .where(
            ChatSession.user_id == user_id,
            ChatSession.project_id == project_id,
        )
        .group_by(ChatSession.id, ChatSession.created_at)
        .order_by(ChatSession.created_at.desc())
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    session_responses = [
        ChatSessionResponse(
            id=row.id,
            created_at=row.created_at,
            message_count=row.message_count,
        )
        for row in rows
    ]
    
    logger.info(f"Listed {len(session_responses)} chat sessions for project: project_id={project_id}")
    
    return ChatSessionListResponse(sessions=session_responses, total=len(session_responses))


@router.get("/sessions/{session_id}/messages/", response_model=MessageListResponse)
async def get_project_messages(
    project_id: UUID,
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    project: UserProject = Depends(get_project_with_validation),
    workspace: UserWorkerSpace = Depends(get_worker_space),
    limit: int = 50,
    offset: int = 0,
) -> MessageListResponse:
    """Get messages for a session in project.
    
    Returns only user-facing messages (user, assistant, system roles).
    Excludes internal system events (TOOL_REQUEST, TOOL_RESULT, CONTEXT_RETRIEVED, etc.)
    which are available through the analytics API.
    """
    user_id = get_current_user_id(request)
    logger.info(f"Getting messages from session: session_id={session_id}, project_id={project_id}")
    
    # Verify session belongs to user and project
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.project_id == project_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        logger.warning(f"Session not found: session_id={session_id}, project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    
    # Define user-facing roles: user, assistant, system (with user-friendly messages)
    USER_FACING_ROLES = ["user", "assistant", "system"]
    
    # Get total count of user-facing messages
    count_result = await db.execute(
        select(func.count(Message.id))
        .where(
            Message.session_id == session_id,
            Message.role.in_(USER_FACING_ROLES)
        )
    )
    total_count = count_result.scalar() or 0
    
    # Get user-facing messages (excluding internal system events)
    result = await db.execute(
        select(Message)
        .where(
            Message.session_id == session_id,
            Message.role.in_(USER_FACING_ROLES)
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    messages = result.scalars().all()
    
    message_responses = [
        MessageResponse(
            id=msg.id,
            role=MessageRole(msg.role),
            content=msg.content,
            agent_id=msg.agent_id,
            timestamp=msg.created_at,
        )
        for msg in reversed(messages)
    ]
    
    return MessageListResponse(
        messages=message_responses,
        total=total_count,
        session_id=session_id,
    )


@router.post("/{session_id}/message/", response_model=MessageResponse)
async def send_project_message(
    project_id: UUID,
    session_id: UUID,
    message_request: MessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    qdrant: AsyncQdrantClient | None = Depends(get_qdrant),
    project: UserProject = Depends(get_project_with_validation),
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> MessageResponse:
    """Send message to chat session in project (direct or orchestrated mode).
    
    Uses unified workspace.handle_message() API which automatically:
    - Routes to direct_execution() if target_agent specified
    - Routes to orchestrated_execution() if no target_agent
    """
    user_id = get_current_user_id(request)
    logger.info(f"Sending message to session: session_id={session_id}, project_id={project_id}")
    
    # Verify session belongs to user and project
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.project_id == project_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        logger.warning(f"Session not found: session_id={session_id}, project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    
    # Get SSE manager
    stream_manager = await get_stream_manager(redis)
    
    # Save user message
    user_message = Message(
        session_id=session_id,
        role=MessageRole.USER.value,
        content=message_request.content,
    )
    db.add(user_message)
    await db.flush()
    
    # Send SSE event: user message created
    await stream_manager.broadcast_event(
        session_id=session_id,
        event=StreamEvent(
            event_type=StreamEventType.MESSAGE_CREATED,
            payload={
                "message_id": str(user_message.id),
                "role": MessageRole.USER.value,
                "content": user_message.content,
                "timestamp": user_message.created_at.isoformat(),
            },
            session_id=session_id,
        ),
    )
    
    # Get session history for workspace execution
    history_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(10)
    )
    history_messages = history_result.scalars().all()
    session_history = [
        {"role": msg.role, "content": msg.content}
        for msg in reversed(history_messages)
    ]
    
    # Parse target agent ID if provided
    target_agent_id = None
    if message_request.target_agent:
        try:
            target_agent_id = UUID(message_request.target_agent)
        except ValueError:
            logger.warning(f"Invalid agent_id: {message_request.target_agent}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="target_agent must be a valid agent UUID",
            )
    
    try:
        # Use unified workspace API
        exec_result = await workspace.handle_message(
            message_content=message_request.content,
            target_agent_id=target_agent_id,
            session_history=session_history,
            task_id=str(session_id),
            session_id=session_id,
        )
        
        # Get agent info for SSE events
        agent_manager = AgentManager(db=db, redis=redis, qdrant=qdrant, user_id=user_id)
        agent_id = target_agent_id or exec_result.get("selected_agent_id")
        
        if agent_id:
            try:
                agent_id_uuid = UUID(str(agent_id))
                agent_response = await agent_manager.get_agent_by_project(
                    agent_id=agent_id_uuid,
                    project_id=project_id,
                )
            except (ValueError, Exception):
                agent_response = None
        else:
            agent_response = None
        
        # Send appropriate SSE events based on mode
        if target_agent_id:
            # Direct mode
            await stream_manager.broadcast_event(
                session_id=session_id,
                event=StreamEvent(
                    event_type=StreamEventType.DIRECT_AGENT_CALL,
                    payload={
                        "agent_id": str(target_agent_id),
                        "agent_name": agent_response.name if agent_response else "Unknown",
                        "message": message_request.content,
                    },
                    session_id=session_id,
                ),
            )
        else:
            # Orchestrated mode
            await stream_manager.broadcast_event(
                session_id=session_id,
                event=StreamEvent(
                    event_type=StreamEventType.TASK_STARTED,
                    payload={
                        "routing_score": exec_result.get("routing_score", 0.0),
                        "selected_agent_id": str(agent_id),
                        "message": message_request.content,
                    },
                    session_id=session_id,
                ),
            )
        
        # Check for execution errors
        if not exec_result.get("success"):
            error_msg = exec_result.get("response", "Unknown error")
            logger.error(f"Execution failed: {error_msg}")
            
            # Send error event
            await stream_manager.broadcast_event(
                session_id=session_id,
                event=StreamEvent(
                    event_type=StreamEventType.ERROR,
                    payload={
                        "agent_id": str(agent_id) if agent_id else "unknown",
                        "error": error_msg,
                        "error_type": "execution_error",
                    },
                    session_id=session_id,
                ),
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Agent execution failed: {error_msg}",
            )
        
        # Save assistant message with structured data support
        # Extract user-friendly response text and optional payload from agent response
        response_text = exec_result.get("response", "")
        payload_data = None
        
        # If response is a JSON string, extract text and store full structure as payload
        if isinstance(response_text, str) and response_text.strip().startswith("{"):
            try:
                response_obj = json.loads(response_text)
                
                if isinstance(response_obj, dict):
                    # Store full structured response as payload
                    payload_data = response_obj
                    
                    # Extract user-friendly text from common fields (priority order)
                    extracted_text = None
                    # Priority 1: Explicit summary field (for structured LLM responses)
                    if "summary" in response_obj and response_obj["summary"]:
                        extracted_text = response_obj["summary"]
                    # Priority 2: Description field
                    elif "description" in response_obj and response_obj["description"]:
                        extracted_text = response_obj["description"]
                    # Priority 3: Title (with optional description)
                    elif "title" in response_obj and response_obj["title"]:
                        if "description" in response_obj and response_obj["description"]:
                            extracted_text = f"{response_obj['title']}\n\n{response_obj['description']}"
                        else:
                            extracted_text = response_obj["title"]
                    # Priority 4: Message field
                    elif "message" in response_obj and response_obj["message"]:
                        extracted_text = response_obj["message"]
                    # Priority 5: Response field
                    elif "response" in response_obj and response_obj["response"]:
                        extracted_text = response_obj["response"]
                    
                    # If we found suitable text, use it; otherwise use compact JSON representation
                    if extracted_text:
                        response_text = extracted_text
                    else:
                        # Generate summary from available fields
                        summary_parts = []
                        for key in ["title", "architecture_decision", "components", "rationale"]:
                            if key in response_obj and response_obj[key]:
                                if isinstance(response_obj[key], dict) and "title" in response_obj[key]:
                                    summary_parts.append(response_obj[key]["title"])
                                elif isinstance(response_obj[key], str) and len(response_obj[key]) < 200:
                                    summary_parts.append(response_obj[key])
                        
                        if summary_parts:
                            response_text = "\n".join(summary_parts)
                        else:
                            # Last resort: create minimal summary
                            response_text = f"Architecture decision prepared ({len(response_obj)} fields)"
            except (json.JSONDecodeError, TypeError):
                # Not valid JSON, use original response as-is
                pass
        
        assistant_message = Message(
            session_id=session_id,
            role=MessageRole.ASSISTANT.value,
            content=response_text,
            payload=payload_data,
            agent_id=UUID(str(agent_id)) if agent_id else None,
        )
        db.add(assistant_message)
        await db.flush()
        
        # Send SSE event: message created
        await stream_manager.broadcast_event(
            session_id=session_id,
            event=StreamEvent(
                event_type=StreamEventType.MESSAGE_CREATED,
                payload={
                    "message_id": str(assistant_message.id),
                    "role": MessageRole.ASSISTANT.value,
                    "content": assistant_message.content,
                    "agent_id": str(agent_id) if agent_id else None,
                    "agent_name": agent_response.name if agent_response else "System",
                    "timestamp": assistant_message.created_at.isoformat(),
                    "context_used": exec_result.get("context_used", 0),
                    "tokens_used": exec_result.get("tokens_used", 0),
                    "execution_time_ms": exec_result.get("execution_time_ms", 0),
                },
                session_id=session_id,
            ),
        )
        
        # Send SSE event: task completed
        await stream_manager.broadcast_event(
            session_id=session_id,
            event=StreamEvent(
                event_type=StreamEventType.TASK_COMPLETED,
                payload={
                    "agent_id": str(agent_id) if agent_id else "system",
                    "agent_name": agent_response.name if agent_response else "System",
                    "status": "success",
                    "response_preview": exec_result.get("response", "")[:200],
                    "execution_time_ms": exec_result.get("execution_time_ms", 0),
                },
                session_id=session_id,
            ),
        )
        
        logger.info(
            f"Message processed successfully: session_id={session_id}, "
            f"agent_id={agent_id}, execution_time_ms={exec_result.get('execution_time_ms')}, "
            f"project_id={project_id}"
        )
        
        return MessageResponse(
            id=assistant_message.id,
            role=MessageRole.ASSISTANT,
            content=assistant_message.content,
            agent_id=assistant_message.agent_id,
            timestamp=assistant_message.created_at,
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid request: {e}")
        await stream_manager.broadcast_event(
            session_id=session_id,
            event=StreamEvent(
                event_type=StreamEventType.ERROR,
                payload={
                    "error_type": "validation_error",
                    "error": str(e),
                },
                session_id=session_id,
            ),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await stream_manager.broadcast_event(
            session_id=session_id,
            event=StreamEvent(
                event_type=StreamEventType.ERROR,
                payload={
                    "error_type": "internal",
                    "error": str(e),
                },
                session_id=session_id,
            ),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}",
        )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_session(
    project_id: UUID,
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    project: UserProject = Depends(get_project_with_validation),
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> None:
    """Delete chat session in project."""
    user_id = get_current_user_id(request)
    logger.info(f"Deleting chat session: session_id={session_id}, project_id={project_id}")
    
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.project_id == project_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        logger.warning(f"Session not found for deletion: session_id={session_id}, project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    
    await db.delete(session)
    await db.flush()
    
    logger.info(f"Chat session deleted: session_id={session_id}, project_id={project_id}")
