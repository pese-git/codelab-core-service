"""Tests for per-project agent management endpoints."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import User, UserProject, UserAgent
from app.schemas.agent import AgentConfig


@pytest.mark.asyncio
async def test_create_agent_in_project():
    """Test creating agent in a specific project."""
    async with AsyncSessionLocal() as db:
        # Create test user and project
        user_id = uuid4()
        project_id = uuid4()
        
        test_user = User(id=user_id, email=f"test-{user_id}@example.com")
        test_project = UserProject(
            id=project_id,
            user_id=user_id,
            name="Test Project",
            workspace_path="/test/workspace",
        )
        db.add(test_user)
        db.add(test_project)
        await db.flush()
        
        # Verify project was created
        result = await db.execute(
            select(UserProject).where(UserProject.id == project_id)
        )
        project = result.scalar_one_or_none()
        assert project is not None
        assert project.user_id == user_id


@pytest.mark.asyncio
async def test_list_agents_by_project():
    """Test listing agents for a specific project."""
    async with AsyncSessionLocal() as db:
        # Create test user and two projects
        user_id = uuid4()
        project_id_1 = uuid4()
        project_id_2 = uuid4()
        
        test_user = User(id=user_id, email=f"test-{user_id}@example.com")
        project_1 = UserProject(
            id=project_id_1,
            user_id=user_id,
            name="Project 1",
            workspace_path="/test/workspace1",
        )
        project_2 = UserProject(
            id=project_id_2,
            user_id=user_id,
            name="Project 2",
            workspace_path="/test/workspace2",
        )
        db.add(test_user)
        db.add(project_1)
        db.add(project_2)
        await db.flush()
        
        # Create agents in both projects
        agent_1 = UserAgent(
            user_id=user_id,
            project_id=project_id_1,
            name="Agent1",
            config={"model": "gpt-4", "temperature": 0.7},
            status="ready",
        )
        agent_2 = UserAgent(
            user_id=user_id,
            project_id=project_id_1,
            name="Agent2",
            config={"model": "gpt-4", "temperature": 0.5},
            status="ready",
        )
        agent_3 = UserAgent(
            user_id=user_id,
            project_id=project_id_2,
            name="Agent3",
            config={"model": "gpt-4", "temperature": 0.3},
            status="ready",
        )
        db.add(agent_1)
        db.add(agent_2)
        db.add(agent_3)
        await db.commit()
        
        # Verify agents are correctly assigned to projects
        result = await db.execute(
            select(UserAgent).where(UserAgent.project_id == project_id_1)
        )
        project_1_agents = result.scalars().all()
        assert len(project_1_agents) == 2
        assert all(a.project_id == project_id_1 for a in project_1_agents)
        
        result = await db.execute(
            select(UserAgent).where(UserAgent.project_id == project_id_2)
        )
        project_2_agents = result.scalars().all()
        assert len(project_2_agents) == 1
        assert project_2_agents[0].project_id == project_id_2


@pytest.mark.asyncio
async def test_agent_belongs_to_correct_project():
    """Test that agents are properly isolated by project."""
    async with AsyncSessionLocal() as db:
        user_id = uuid4()
        project_id_1 = uuid4()
        project_id_2 = uuid4()
        
        test_user = User(id=user_id, email=f"test-{user_id}@example.com")
        project_1 = UserProject(
            id=project_id_1,
            user_id=user_id,
            name="Project 1",
            workspace_path="/test/workspace1",
        )
        project_2 = UserProject(
            id=project_id_2,
            user_id=user_id,
            name="Project 2",
            workspace_path="/test/workspace2",
        )
        db.add(test_user)
        db.add(project_1)
        db.add(project_2)
        await db.flush()
        
        agent_id_1 = uuid4()
        agent_id_2 = uuid4()
        
        agent_1 = UserAgent(
            id=agent_id_1,
            user_id=user_id,
            project_id=project_id_1,
            name="ProjectAgent1",
            config={"model": "gpt-4"},
            status="ready",
        )
        agent_2 = UserAgent(
            id=agent_id_2,
            user_id=user_id,
            project_id=project_id_2,
            name="ProjectAgent2",
            config={"model": "gpt-4"},
            status="ready",
        )
        db.add(agent_1)
        db.add(agent_2)
        await db.commit()
        
        # Verify agent 1 is only in project 1
        result = await db.execute(
            select(UserAgent).where(
                (UserAgent.id == agent_id_1) & (UserAgent.project_id == project_id_1)
            )
        )
        agent = result.scalar_one_or_none()
        assert agent is not None
        
        # Verify agent 1 is NOT in project 2
        result = await db.execute(
            select(UserAgent).where(
                (UserAgent.id == agent_id_1) & (UserAgent.project_id == project_id_2)
            )
        )
        agent = result.scalar_one_or_none()
        assert agent is None


@pytest.mark.asyncio
async def test_user_isolation_in_projects():
    """Test that users cannot access each other's project agents."""
    async with AsyncSessionLocal() as db:
        # Create two users
        user_1_id = uuid4()
        user_2_id = uuid4()
        
        user_1 = User(id=user_1_id, email=f"user1-{user_1_id}@example.com")
        user_2 = User(id=user_2_id, email=f"user2-{user_2_id}@example.com")
        
        db.add(user_1)
        db.add(user_2)
        await db.flush()
        
        # Create projects for each user
        user_1_project_id = uuid4()
        user_2_project_id = uuid4()
        
        user_1_project = UserProject(
            id=user_1_project_id,
            user_id=user_1_id,
            name="User1 Project",
            workspace_path="/test/user1",
        )
        user_2_project = UserProject(
            id=user_2_project_id,
            user_id=user_2_id,
            name="User2 Project",
            workspace_path="/test/user2",
        )
        db.add(user_1_project)
        db.add(user_2_project)
        await db.flush()
        
        # Create agents for each user's project
        user_1_agent = UserAgent(
            user_id=user_1_id,
            project_id=user_1_project_id,
            name="User1Agent",
            config={"model": "gpt-4"},
            status="ready",
        )
        user_2_agent = UserAgent(
            user_id=user_2_id,
            project_id=user_2_project_id,
            name="User2Agent",
            config={"model": "gpt-4"},
            status="ready",
        )
        db.add(user_1_agent)
        db.add(user_2_agent)
        await db.commit()
        
        # Verify User 1 can only see their agents
        result = await db.execute(
            select(UserAgent).where(UserAgent.user_id == user_1_id)
        )
        user_1_agents = result.scalars().all()
        assert len(user_1_agents) == 1
        assert user_1_agents[0].user_id == user_1_id
        
        # Verify User 2 can only see their agents
        result = await db.execute(
            select(UserAgent).where(UserAgent.user_id == user_2_id)
        )
        user_2_agents = result.scalars().all()
        assert len(user_2_agents) == 1
        assert user_2_agents[0].user_id == user_2_id
