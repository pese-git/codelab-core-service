"""Helper functions for agent discovery and management."""

from uuid import UUID
from typing import Optional
from sqlalchemy import cast, String, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_agent import UserAgent
from app.schemas.agent_role import AgentRole


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


async def get_orchestrator(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    status: str = "ready"
) -> Optional[UserAgent]:
    """Get the orchestrator agent for a project.
    
    The orchestrator is a special UserAgent with role='orchestrator'
    that coordinates execution of other agents.
    
    Args:
        db: Database session
        user_id: User ID
        project_id: Project ID
        status: Agent status to filter by (default: "ready")
    
    Returns:
        UserAgent with role='orchestrator' or None if not found.
    
    Raises:
        ValueError: If multiple orchestrators found (shouldn't happen)
    
    Example:
        orchestrator = await get_orchestrator(db, user_id, project_id)
        if orchestrator:
            result = await workspace.direct_execution(
                agent_id=orchestrator.id,
                user_message="..."
            )
    """
    result = await db.execute(
        select(UserAgent)
        .where(UserAgent.user_id == user_id)
        .where(UserAgent.project_id == project_id)
        .where(UserAgent.status == status)
        .where(
            cast(
                UserAgent.config['metadata']['role'],
                String
            ) == AgentRole.ORCHESTRATOR.value
        )
    )
    return result.scalar_one_or_none()


async def get_agents_by_role(
    db: AsyncSession,
    project_id: UUID,
    role: AgentRole,
    status: str = "ready",
    user_id: Optional[UUID] = None
) -> list[UserAgent]:
    """Get all agents with a specific role.
    
    Args:
        db: Database session
        project_id: Project ID
        role: Agent role to filter by
        status: Agent status to filter by (default: "ready")
        user_id: Optional user ID for additional filtering
    
    Returns:
        List of agents matching the criteria.
    
    Example:
        code_agents = await get_agents_by_role(
            db, project_id, AgentRole.CODE
        )
        for agent in code_agents:
            print(agent.name)
    """
    query = select(UserAgent).where(
        UserAgent.project_id == project_id,
        UserAgent.status == status,
        cast(
            UserAgent.config['metadata']['role'],
            String
        ) == role.value
    )
    
    if user_id:
        query = query.where(UserAgent.user_id == user_id)
    
    result = await db.execute(query)
    return result.scalars().all()


async def get_agents_by_capability(
    db: AsyncSession,
    project_id: UUID,
    capability: str,
    status: str = "ready",
    user_id: Optional[UUID] = None
) -> list[UserAgent]:
    """Get all agents with a specific capability.
    
    Args:
        db: Database session
        project_id: Project ID
        capability: Capability to search for (e.g., 'debug', 'implement_feature')
        status: Agent status to filter by (default: "ready")
        user_id: Optional user ID for additional filtering
    
    Returns:
        List of agents with the requested capability.
    
    Example:
        debug_agents = await get_agents_by_capability(
            db, project_id, "debug"
        )
    """
    # Fetch all ready agents for the project
    query = select(UserAgent).where(
        UserAgent.project_id == project_id,
        UserAgent.status == status,
    )
    
    if user_id:
        query = query.where(UserAgent.user_id == user_id)
    
    result = await db.execute(query)
    agents = result.scalars().all()
    
    # Filter agents that have the requested capability
    matching_agents = []
    for agent in agents:
        capabilities = agent.config.get("metadata", {}).get("capabilities", [])
        if capability in capabilities:
            matching_agents.append(agent)
    
    return matching_agents
