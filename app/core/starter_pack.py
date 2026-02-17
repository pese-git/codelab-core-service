"""Default Starter Pack configuration for new projects."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_agent import UserAgent


# Default agents configuration for new projects
DEFAULT_AGENTS_CONFIG = [
    {
        "name": "CodeAssistant",
        "config": {
            "model": "openrouter/openai/gpt-4.1",
            "temperature": 0.7,
            "system_prompt": "You are a helpful coding assistant specialized in Python and web development.",
            "tools": ["code_search", "file_operations", "terminal"],
        },
    },
    {
        "name": "DataAnalyst",
        "config": {
            "model": "openrouter/openai/gpt-4.1",
            "temperature": 0.3,
            "system_prompt": "You are a data analyst expert. Help users analyze data and create visualizations.",
            "tools": ["data_analysis", "visualization", "statistics"],
        },
    },
    {
        "name": "DocumentWriter",
        "config": {
            "model": "openrouter/openai/gpt-4.1",
            "temperature": 0.8,
            "system_prompt": "You are a technical writer. Help users create clear and comprehensive documentation.",
            "tools": ["markdown", "diagrams", "templates"],
        },
    },
]


async def initialize_starter_pack(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
) -> list[UserAgent]:
    """Initialize default agents for a new project.

    Creates the Default Starter Pack with pre-configured agents when a new project is created.

    Args:
        db: Database session
        user_id: ID of the user who owns the project
        project_id: ID of the project to initialize

    Returns:
        List of created UserAgent instances

    Example:
        agents = await initialize_starter_pack(db, user_id, project_id)
        # agents is now a list of 3 UserAgent objects
    """
    created_agents = []

    for agent_config in DEFAULT_AGENTS_CONFIG:
        agent = UserAgent(
            user_id=user_id,
            project_id=project_id,
            name=agent_config["name"],
            config=agent_config["config"],
            status="ready",
        )
        db.add(agent)
        created_agents.append(agent)

    # Flush to ensure agents are created but not committed yet
    # The caller will commit the transaction
    await db.flush()

    return created_agents


def get_starter_pack_config() -> dict[str, Any]:
    """Get the full starter pack configuration.

    Returns:
        Dictionary containing the starter pack configuration

    Example:
        config = get_starter_pack_config()
        agents_count = len(config["agents"])
    """
    return {
        "name": "Default Starter Pack",
        "description": "Default set of agents for new projects",
        "agents": DEFAULT_AGENTS_CONFIG,
        "agents_count": len(DEFAULT_AGENTS_CONFIG),
    }
