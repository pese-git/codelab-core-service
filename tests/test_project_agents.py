"""Tests for per-project agent management endpoints."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserProject, UserAgent


@pytest.mark.asyncio
async def test_create_agent_in_project(db_session: AsyncSession, test_user: User, test_project: UserProject):
    """Test creating agent in a specific project."""
    # Create test agent in project
    agent = UserAgent(
        user_id=test_user.id,
        project_id=test_project.id,
        name="Test Agent",
        config={"model": "gpt-4", "temperature": 0.7},
        status="ready",
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    
    # Verify agent was created with correct project
    result = await db_session.execute(
        select(UserAgent).where(UserAgent.id == agent.id)
    )
    retrieved_agent = result.scalar_one_or_none()
    assert retrieved_agent is not None
    assert retrieved_agent.project_id == test_project.id
    assert retrieved_agent.user_id == test_user.id


@pytest.mark.asyncio
async def test_list_agents_by_project(db_session: AsyncSession, test_user: User):
    """Test listing agents for a specific project."""
    # Create two projects
    project_1 = UserProject(
        user_id=test_user.id,
        name="Project 1",
        workspace_path="/test/workspace1",
    )
    project_2 = UserProject(
        user_id=test_user.id,
        name="Project 2",
        workspace_path="/test/workspace2",
    )
    db_session.add(project_1)
    db_session.add(project_2)
    await db_session.flush()
    
    # Create agents in both projects
    agent_1 = UserAgent(
        user_id=test_user.id,
        project_id=project_1.id,
        name="Agent1",
        config={"model": "gpt-4", "temperature": 0.7},
        status="ready",
    )
    agent_2 = UserAgent(
        user_id=test_user.id,
        project_id=project_1.id,
        name="Agent2",
        config={"model": "gpt-4", "temperature": 0.5},
        status="ready",
    )
    agent_3 = UserAgent(
        user_id=test_user.id,
        project_id=project_2.id,
        name="Agent3",
        config={"model": "gpt-4", "temperature": 0.3},
        status="ready",
    )
    db_session.add(agent_1)
    db_session.add(agent_2)
    db_session.add(agent_3)
    await db_session.commit()
    
    # Verify agents are correctly assigned to projects
    result = await db_session.execute(
        select(UserAgent).where(UserAgent.project_id == project_1.id)
    )
    project_1_agents = result.scalars().all()
    assert len(project_1_agents) == 2
    assert all(a.project_id == project_1.id for a in project_1_agents)
    
    result = await db_session.execute(
        select(UserAgent).where(UserAgent.project_id == project_2.id)
    )
    project_2_agents = result.scalars().all()
    assert len(project_2_agents) == 1
    assert project_2_agents[0].project_id == project_2.id


@pytest.mark.asyncio
async def test_agent_belongs_to_correct_project(db_session: AsyncSession, test_user: User):
    """Test that agents are properly isolated by project."""
    # Create two projects
    project_1 = UserProject(
        user_id=test_user.id,
        name="Project 1",
        workspace_path="/test/workspace1",
    )
    project_2 = UserProject(
        user_id=test_user.id,
        name="Project 2",
        workspace_path="/test/workspace2",
    )
    db_session.add(project_1)
    db_session.add(project_2)
    await db_session.flush()
    
    # Create agents in different projects
    agent_1 = UserAgent(
        user_id=test_user.id,
        project_id=project_1.id,
        name="ProjectAgent1",
        config={"model": "gpt-4"},
        status="ready",
    )
    agent_2 = UserAgent(
        user_id=test_user.id,
        project_id=project_2.id,
        name="ProjectAgent2",
        config={"model": "gpt-4"},
        status="ready",
    )
    db_session.add(agent_1)
    db_session.add(agent_2)
    await db_session.commit()
    
    # Verify agent 1 is only in project 1
    result = await db_session.execute(
        select(UserAgent).where(
            (UserAgent.id == agent_1.id) & (UserAgent.project_id == project_1.id)
        )
    )
    agent = result.scalar_one_or_none()
    assert agent is not None
    
    # Verify agent 1 is NOT in project 2
    result = await db_session.execute(
        select(UserAgent).where(
            (UserAgent.id == agent_1.id) & (UserAgent.project_id == project_2.id)
        )
    )
    agent = result.scalar_one_or_none()
    assert agent is None


@pytest.mark.asyncio
async def test_user_isolation_in_projects(db_session: AsyncSession):
    """Test that users cannot access each other's project agents."""
    # Create two users
    user_1 = User(email="user1@example.com")
    user_2 = User(email="user2@example.com")
    
    db_session.add(user_1)
    db_session.add(user_2)
    await db_session.flush()
    
    # Create projects for each user
    user_1_project = UserProject(
        user_id=user_1.id,
        name="User1 Project",
        workspace_path="/test/user1",
    )
    user_2_project = UserProject(
        user_id=user_2.id,
        name="User2 Project",
        workspace_path="/test/user2",
    )
    db_session.add(user_1_project)
    db_session.add(user_2_project)
    await db_session.flush()
    
    # Create agents for each user's project
    user_1_agent = UserAgent(
        user_id=user_1.id,
        project_id=user_1_project.id,
        name="User1Agent",
        config={"model": "gpt-4"},
        status="ready",
    )
    user_2_agent = UserAgent(
        user_id=user_2.id,
        project_id=user_2_project.id,
        name="User2Agent",
        config={"model": "gpt-4"},
        status="ready",
    )
    db_session.add(user_1_agent)
    db_session.add(user_2_agent)
    await db_session.commit()
    
    # Verify User 1 can only see their agents
    result = await db_session.execute(
        select(UserAgent).where(UserAgent.user_id == user_1.id)
    )
    user_1_agents = result.scalars().all()
    assert len(user_1_agents) == 1
    assert user_1_agents[0].user_id == user_1.id
    
    # Verify User 2 can only see their agents
    result = await db_session.execute(
        select(UserAgent).where(UserAgent.user_id == user_2.id)
    )
    user_2_agents = result.scalars().all()
    assert len(user_2_agents) == 1
    assert user_2_agents[0].user_id == user_2.id
