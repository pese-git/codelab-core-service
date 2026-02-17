"""Test project creation with Default Starter Pack."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import User, UserProject, UserAgent
from app.schemas.project import ProjectCreate


@pytest.mark.asyncio
async def test_create_project_with_starter_pack():
    """Test that creating a project initializes default starter pack agents."""
    async with AsyncSessionLocal() as db:
        # Create test user
        user_id = uuid4()
        test_user = User(
            id=user_id,
            email=f"test-{user_id}@example.com"
        )
        db.add(test_user)
        await db.flush()

        # Create project via API (simulated)
        project_data = ProjectCreate(
            name="Test Project",
            workspace_path="/test/workspace"
        )
        
        # Create project directly using the same logic as endpoint
        from app.core.starter_pack import initialize_starter_pack
        
        project = UserProject(
            user_id=user_id,
            name=project_data.name,
            workspace_path=project_data.workspace_path,
        )
        db.add(project)
        await db.flush()

        # Initialize starter pack
        agents = await initialize_starter_pack(db, user_id, project.id)
        await db.commit()
        await db.refresh(project)

        # Verify project was created
        result = await db.execute(
            select(UserProject).where(UserProject.id == project.id)
        )
        created_project = result.scalar_one_or_none()
        assert created_project is not None
        assert created_project.name == "Test Project"
        assert created_project.workspace_path == "/test/workspace"

        # Verify agents were created
        assert len(agents) == 3
        agent_names = [agent.name for agent in agents]
        assert "CodeAssistant" in agent_names
        assert "DataAnalyst" in agent_names
        assert "DocumentWriter" in agent_names

        # Verify all agents belong to the project
        for agent in agents:
            assert agent.user_id == user_id
            assert agent.project_id == project.id
            assert agent.status == "ready"

        # Verify agents can be queried from database
        result = await db.execute(
            select(UserAgent).where(UserAgent.project_id == project.id)
        )
        db_agents = result.scalars().all()
        assert len(db_agents) == 3


@pytest.mark.asyncio
async def test_starter_pack_configuration():
    """Test that starter pack configuration is correct."""
    from app.core.starter_pack import get_starter_pack_config, DEFAULT_AGENTS_CONFIG

    config = get_starter_pack_config()
    
    assert config["name"] == "Default Starter Pack"
    assert config["agents_count"] == 3
    assert len(config["agents"]) == 3
    
    # Verify each agent has required fields
    for agent_config in config["agents"]:
        assert "name" in agent_config
        assert "config" in agent_config
        assert agent_config["config"]["model"] is not None
        assert agent_config["config"]["temperature"] is not None
        assert agent_config["config"]["system_prompt"] is not None
        assert agent_config["config"]["tools"] is not None


