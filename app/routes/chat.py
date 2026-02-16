"""Chat endpoints."""

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
from app.middleware.user_isolation import get_current_user_id
from app.models.chat_session import ChatSession
from app.models.message import Message
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
from app.schemas.event import StreamEvent, StreamEventType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/my/chat", tags=["chat"])


@router.post("/sessions/", status_code=status.HTTP_201_CREATED, response_model=ChatSessionResponse)
async def create_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """Create new chat session."""
    user_id = get_current_user_id(request)
    
    session = ChatSession(user_id=user_id)
    db.add(session)
    await db.flush()
    
    return ChatSessionResponse(
        id=session.id,
        created_at=session.created_at,
        message_count=0,
    )


@router.get("/sessions/", response_model=ChatSessionListResponse)
async def list_sessions(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ChatSessionListResponse:
    """List all user chat sessions."""
    user_id = get_current_user_id(request)
    
    # Get sessions with message count using subquery
    stmt = (
        select(
            ChatSession.id,
            ChatSession.created_at,
            func.count(Message.id).label('message_count')
        )
        .outerjoin(Message, Message.session_id == ChatSession.id)
        .where(ChatSession.user_id == user_id)
        .group_by(ChatSession.id, ChatSession.created_at)
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
    
    return ChatSessionListResponse(sessions=session_responses, total=len(session_responses))


@router.get("/sessions/{session_id}/messages/", response_model=MessageListResponse)
async def get_messages(
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> MessageListResponse:
    """Get messages for a session."""
    user_id = get_current_user_id(request)
    
    # Verify session belongs to user
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
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
async def send_message(
    session_id: UUID,
    message_request: MessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
) -> MessageResponse:
    """Send message to chat session (direct or orchestrated mode)."""
    user_id = get_current_user_id(request)
    
    # Verify session belongs to user
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
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
    
    # Direct mode: target_agent specified
    if message_request.target_agent:
        # Get agent manager
        agent_manager = AgentManager(db=db, redis=redis, qdrant=qdrant, user_id=user_id)
        agent_response = await agent_manager.get_agent_by_name(message_request.target_agent)
        
        if not agent_response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{message_request.target_agent}' not found",
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
                # Send error event
                await stream_manager.broadcast_event(
                    session_id=session_id,
                    event=StreamEvent(
                        event_type=StreamEventType.TASK_COMPLETED,
                        payload={
                            "agent_id": str(agent_response.id),
                            "status": "error",
                            "error": result.get("error"),
                        },
                        session_id=session_id,
                    ),
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Agent execution failed: {result.get('error')}",
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
            
            logger.info(f"Message processed successfully: session={session_id}, agent={agent_response.name}")
            
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
            logger.error(f"Error processing message: {e}")
            # Send error event
            await stream_manager.broadcast_event(
                session_id=session_id,
                event=StreamEvent(
                    event_type=StreamEventType.TASK_COMPLETED,
                    payload={
                        "agent_id": str(agent_response.id),
                        "status": "error",
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
    
    return MessageResponse(
        id=assistant_message.id,
        role=MessageRole.ASSISTANT,
        content=assistant_message.content,
        agent_id=None,
        timestamp=assistant_message.created_at,
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete chat session."""
    user_id = get_current_user_id(request)
    
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    
    await db.delete(session)
    await db.flush()
