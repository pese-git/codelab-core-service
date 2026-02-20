"""Helper functions for agent discovery and management."""

from uuid import UUID
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_agent import UserAgent


async def find_agent_by_role(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    role: str
) -> Optional[UUID]:
    """Find agent by metadata.role field.
    
    Searches for an agent with a specific role within a user's project.
    Only returns agents with 'ready' status.
    
    Args:
        db: Database session
        user_id: ID of the user who owns the agent
        project_id: ID of the project containing the agent
        role: Role to search for (e.g., 'architect', 'orchestrator', 'executor')
    
    Returns:
        Agent ID if found, None otherwise
    
    Example:
        architect_id = await find_agent_by_role(
            db, user_id, project_id, "architect"
        )
    """
    result = await db.execute(
        select(UserAgent).where(
            UserAgent.user_id == user_id,
            UserAgent.project_id == project_id,
            UserAgent.status == "ready"
        )
    )
    agents = result.scalars().all()
    
    for agent in agents:
        if agent.config.get("metadata", {}).get("role") == role:
            return agent.id
    
    return None


async def find_agent_by_name(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    name: str
) -> Optional[UUID]:
    """Find agent by name.
    
    Searches for an agent with a specific name within a user's project.
    Only returns agents with 'ready' status.
    
    Args:
        db: Database session
        user_id: ID of the user who owns the agent
        project_id: ID of the project containing the agent
        name: Agent name to search for (e.g., 'Architect', 'CodeAssistant')
    
    Returns:
        Agent ID if found, None otherwise
    
    Example:
        code_assistant_id = await find_agent_by_name(
            db, user_id, project_id, "CodeAssistant"
        )
    """
    result = await db.execute(
        select(UserAgent).where(
            UserAgent.user_id == user_id,
            UserAgent.project_id == project_id,
            UserAgent.name == name,
            UserAgent.status == "ready"
        )
    )
    agent = result.scalar_one_or_none()
    
    return agent.id if agent else None
