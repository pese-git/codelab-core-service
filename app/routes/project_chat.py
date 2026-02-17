"""Per-project chat endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.contextual_agent import ContextualAgent
from app.agents.manager import AgentManager
from app.core.stream_manager import get_stream_manager
from app.database import get_db
from app.middleware.project_validation import get_project_with_validation
from app.middleware.user_isolation import get_current_user_id
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.user_project import UserProject
from app.qdrant_client import get_qdrant
from app.redis_client import get_redis
from app.schemas.agent import AgentConfig
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
    limit: int = 50,
    offset: int = 0,
) -> MessageListResponse:
    """Get messages for a session in project."""
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
    
    # Get total count of messages
    count_result = await db.execute(
        select(func.count(Message.id))
        .where(Message.session_id == session_id)
    )
    total_count = count_result.scalar() or 0
    
    # Get messages
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
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
) -> MessageResponse:
    """Send message to chat session in project (direct or orchestrated mode)."""
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
    
    # Direct mode: target_agent specified
    if message_request.target_agent:
        # Get agent manager with project context
        agent_manager = AgentManager(db=db, redis=redis, qdrant=qdrant, user_id=user_id)
        try:
            target_agent_uuid = UUID(message_request.target_agent)
            agent_response = await agent_manager.get_agent_by_project(
                agent_id=target_agent_uuid,
                project_id=project_id,
            )
        except ValueError:
            # If not a valid UUID, treat as error
            logger.warning(f"Invalid agent_id: {message_request.target_agent}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="target_agent must be a valid agent UUID",
            )
        
        if not agent_response:
            logger.warning(f"Agent not found: agent_id={message_request.target_agent}, project_id={project_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{message_request.target_agent}' not found in this project",
            )
        
        # Send SSE event: direct agent call started
        await stream_manager.broadcast_event(
            session_id=session_id,
            event=StreamEvent(
                event_type=StreamEventType.DIRECT_AGENT_CALL,
                payload={
                    "agent_id": str(agent_response.id),
                    "agent_name": agent_response.name,
                    "message": message_request.content,
                },
                session_id=session_id,
            ),
        )
        
        # Create contextual agent
        contextual_agent = ContextualAgent(
            agent_id=agent_response.id,
            user_id=user_id,
            config=agent_response.config,
            qdrant_client=qdrant,
        )
        
        # Get session history
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(10)
        )
        history_messages = result.scalars().all()
        session_history = [
            {"role": msg.role, "content": msg.content}
            for msg in reversed(history_messages)
        ]
        
        # Send SSE event: task started
        await stream_manager.broadcast_event(
            session_id=session_id,
            event=StreamEvent(
                event_type=StreamEventType.TASK_STARTED,
                payload={
                    "agent_id": str(agent_response.id),
                    "agent_name": agent_response.name,
                    "task_description": f"Processing message: {message_request.content[:100]}...",
                },
                session_id=session_id,
            ),
        )
        
        # Execute agent
        try:
            result = await contextual_agent.execute(
                user_message=message_request.content,
                session_history=session_history,
                task_id=str(session_id),
            )
            
            if not result["success"]:
                error_type = result.get("error_type", "unknown")
                error_msg = result.get("error")
                provider = result.get("provider", "unknown")
                model = result.get("model", agent_response.config.model)
                
                # Send detailed error event
                await stream_manager.broadcast_event(
                    session_id=session_id,
                    event=StreamEvent(
                        event_type=StreamEventType.ERROR,
                        payload={
                            "agent_id": str(agent_response.id),
                            "agent_name": agent_response.name,
                            "error_type": error_type,
                            "error": error_msg,
                            "provider": provider,
                            "model": model,
                        },
                        session_id=session_id,
                    ),
                )
                
                # Return detailed error response
                if error_type in ["timeout", "connection", "rate_limit", "authentication", "bad_request"]:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=LLMProviderError(
                            detail=error_msg,
                            error_code="LLM_PROVIDER_ERROR",
                            metadata={
                                "provider": provider,
                                "model": model,
                                "error_type": error_type,
                                "agent_id": str(agent_response.id),
                                "agent_name": agent_response.name,
                            }
                        ).model_dump(),
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Agent execution failed: {error_msg}",
                    )
            
            # Send context retrieved event if context was used
            if result.get("context"):
                await stream_manager.broadcast_event(
                    session_id=session_id,
                    event=StreamEvent(
                        event_type=StreamEventType.CONTEXT_RETRIEVED,
                        payload={
                            "agent_id": str(agent_response.id),
                            "context_count": len(result["context"]),
                            "context_preview": result["context"][:200] if result["context"] else "",
                        },
                        session_id=session_id,
                    ),
                )
            
            # Save assistant message
            assistant_message = Message(
                session_id=session_id,
                role=MessageRole.ASSISTANT.value,
                content=result["response"],
                agent_id=agent_response.id,
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
                        "agent_id": str(agent_response.id),
                        "agent_name": agent_response.name,
                        "timestamp": assistant_message.created_at.isoformat(),
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
                        "agent_id": str(agent_response.id),
                        "agent_name": agent_response.name,
                        "status": "success",
                        "response_preview": result["response"][:200],
                    },
                    session_id=session_id,
                ),
            )
            
            logger.info(f"Message processed successfully: session_id={session_id}, agent={agent_response.name}, project_id={project_id}")
            
            return MessageResponse(
                id=assistant_message.id,
                role=MessageRole.ASSISTANT,
                content=assistant_message.content,
                agent_id=assistant_message.agent_id,
                timestamp=assistant_message.created_at,
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            # Send error event
            await stream_manager.broadcast_event(
                session_id=session_id,
                event=StreamEvent(
                    event_type=StreamEventType.ERROR,
                    payload={
                        "agent_id": str(agent_response.id),
                        "agent_name": agent_response.name,
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
    
    # Orchestrated mode: TODO - implement orchestrator
    # For MVP, return a placeholder response
    assistant_message = Message(
        session_id=session_id,
        role=MessageRole.ASSISTANT.value,
        content="Orchestrated mode not yet implemented. Please specify target_agent for direct mode.",
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
                "timestamp": assistant_message.created_at.isoformat(),
            },
            session_id=session_id,
        ),
    )
    
    return MessageResponse(
        id=assistant_message.id,
        role=MessageRole.ASSISTANT,
        content=assistant_message.content,
        agent_id=None,
        timestamp=assistant_message.created_at,
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_session(
    project_id: UUID,
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    project: UserProject = Depends(get_project_with_validation),
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
