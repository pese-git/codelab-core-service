"""Default Starter Pack configuration for new projects."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_agent import UserAgent


# Default agents configuration for new projects
DEFAULT_AGENTS_CONFIG = [
    {
        "name": "Architect",
        "config": {
            "model": "openrouter/openai/gpt-4.1",
            "temperature": 0.3,
            "system_prompt": """You are a project architect and task planner.

Your role:
- Analyze user requests and break them down into structured task plans
- Define clear, actionable tasks with priorities
- Identify dependencies between tasks
- Estimate complexity and time requirements
- Create comprehensive project plans

Output format (JSON):
{
  "title": "Plan title",
  "description": "Plan description",
  "tasks": [
    {
      "title": "Task title",
      "description": "Task description",
      "priority": "high|medium|low",
      "estimated_time": "2h",
      "dependencies": [],
      "agent_type": "CodeAssistant|DataAnalyst|DocumentWriter"
    }
  ]
}""",
            "tools": [],
            "concurrency_limit": 3,
            "max_tokens": 4096,
            "metadata": {
                "role": "architect",
                "capabilities": ["planning", "task_breakdown", "dependency_analysis"],
                "risk_level": "LOW",
                "cost_per_call": 0.02,
                "estimated_duration": 10.0,
            },
        },
    },
    {
        "name": "Orchestrator",
        "config": {
            "model": "openrouter/openai/gpt-4.1",
            "temperature": 0.5,
            "system_prompt": """You are a project orchestrator and execution coordinator.

Your role:
- Coordinate execution of task plans
- Select appropriate agents for each task
- Monitor task progress and dependencies
- Handle task failures and retries
- Report execution status

Available agents:
- CodeAssistant: for coding tasks
- DataAnalyst: for data analysis
- DocumentWriter: for documentation
- Architect: for planning and design

When coordinating tasks:
1. Check task dependencies
2. Execute tasks in correct order
3. Pass results between dependent tasks
4. Report progress via events
5. Handle errors gracefully""",
            "tools": [],
            "concurrency_limit": 3,
            "max_tokens": 4096,
            "metadata": {
                "role": "orchestrator",
                "capabilities": ["coordination", "agent_selection", "progress_monitoring"],
                "risk_level": "LOW",
                "cost_per_call": 0.01,
                "estimated_duration": 5.0,
            },
        },
    },
    {
        "name": "CodeAssistant",
        "config": {
            "model": "openrouter/openai/gpt-4.1",
            "temperature": 0.7,
            "system_prompt": "You are a helpful coding assistant specialized in Python and web development.",
            "tools": ["code_search", "file_operations", "terminal"],
            "concurrency_limit": 3,
            "max_tokens": 4096,
            "metadata": {
                "role": "executor",
                "capabilities": ["code_writing", "code_review", "debugging"],
                "risk_level": "MEDIUM",
                "cost_per_call": 0.015,
                "estimated_duration": 5.0,
            },
        },
    },
    {
        "name": "DataAnalyst",
        "config": {
            "model": "openrouter/openai/gpt-4.1",
            "temperature": 0.3,
            "system_prompt": "You are a data analyst expert. Help users analyze data and create visualizations.",
            "tools": ["data_analysis", "visualization", "statistics"],
            "concurrency_limit": 3,
            "max_tokens": 4096,
            "metadata": {
                "role": "executor",
                "capabilities": ["data_analysis", "visualization", "statistics"],
                "risk_level": "LOW",
                "cost_per_call": 0.01,
                "estimated_duration": 8.0,
            },
        },
    },
    {
        "name": "DocumentWriter",
        "config": {
            "model": "openrouter/openai/gpt-4.1",
            "temperature": 0.8,
            "system_prompt": "You are a technical writer. Help users create clear and comprehensive documentation.",
            "tools": ["markdown", "diagrams", "templates"],
            "concurrency_limit": 3,
            "max_tokens": 4096,
            "metadata": {
                "role": "executor",
                "capabilities": ["documentation", "technical_writing", "diagrams"],
                "risk_level": "LOW",
                "cost_per_call": 0.008,
                "estimated_duration": 6.0,
            },
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
