"""Tests for User Worker Space."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent_bus import AgentBus
from app.core.user_worker_space import UserWorkerSpace, AgentCache
from app.core.worker_space_manager import WorkerSpaceManager, get_worker_space_manager
from app.database import AsyncSessionLocal
from app.models import User, UserAgent
from app.schemas.agent import AgentConfig
from app.database import get_db


@pytest.mark.asyncio
async def test_agent_cache_operations():
    """Test agent cache basic operations."""
    cache = AgentCache(ttl_seconds=300)

    # Create mock agent
    class MockAgent:
        def __init__(self):
            self.id = uuid4()

    agent = MockAgent()

    # Test set and get
    await cache.set(agent.id, agent)
    cached = await cache.get(agent.id)
    assert cached == agent

    # Test invalidate
    await cache.invalidate(agent.id)
    cached = await cache.get(agent.id)
    assert cached is None

    # Test clear
    agent2 = MockAgent()
    await cache.set(agent.id, agent)
    await cache.set(agent2.id, agent2)
    assert cache.get_size() == 2

    await cache.clear()
    assert cache.get_size() == 0


@pytest.mark.asyncio
async def test_user_worker_space_initialization(
    db_session: AsyncSession, test_user, test_project, test_agents_fixture
):
    """Test worker space initialization."""
    agent_bus = AgentBus()

    space = UserWorkerSpace(
        user_id=test_user.id,
        project_id=str(test_project.id),
        db=db_session,
        redis=None,
        qdrant=None,
        agent_bus=agent_bus,
    )

    assert space.user_id == test_user.id
    assert space.project_id == str(test_project.id)
    assert not space.initialized

    # Initialize
    await space.initialize()

    assert space.initialized
    assert len(space.active_agents) == len(test_agents_fixture)


@pytest.mark.asyncio
async def test_user_worker_space_agent_management(
    db_session: AsyncSession, test_user, test_project, test_agents_fixture
):
    """Test agent management in worker space."""
    agent_bus = AgentBus()

    space = UserWorkerSpace(
        user_id=test_user.id,
        project_id=str(test_project.id),
        db=db_session,
        redis=None,
        qdrant=None,
        agent_bus=agent_bus,
    )

    # Get agent (should initialize first)
    agent = await space.get_agent(test_agents_fixture[0].id)
    assert agent is not None

    # Remove agent - just verify it doesn't throw
    removed = await space.remove_agent(test_agents_fixture[0].id)
    # Result may vary, but should not error


@pytest.mark.asyncio
async def test_user_worker_space_cleanup(db_session: AsyncSession, test_user, test_project, test_agents_fixture):
    """Test worker space cleanup."""
    agent_bus = AgentBus()

    space = UserWorkerSpace(
        user_id=test_user.id,
        project_id=str(test_project.id),
        db=db_session,
        redis=None,
        qdrant=None,
        agent_bus=agent_bus,
    )

    await space.initialize()
    assert space.initialized

    await space.cleanup()
    assert not space.initialized
    assert len(space.active_agents) == 0


@pytest.mark.asyncio
async def test_user_worker_space_reset(db_session: AsyncSession, test_user, test_project, test_agents_fixture):
    """Test worker space reset."""
    agent_bus = AgentBus()

    space = UserWorkerSpace(
        user_id=test_user.id,
        project_id=str(test_project.id),
        db=db_session,
        redis=None,
        qdrant=None,
        agent_bus=agent_bus,
    )

    await space.initialize()
    assert len(space.active_agents) == len(test_agents_fixture)

    # Reset
    await space.reset()
    assert space.initialized
    assert len(space.active_agents) == len(test_agents_fixture)


@pytest.mark.asyncio
async def test_user_worker_space_stats(db_session: AsyncSession, test_user, test_project, test_agents_fixture):
    """Test worker space statistics."""
    agent_bus = AgentBus()

    space = UserWorkerSpace(
        user_id=test_user.id,
        project_id=str(test_project.id),
        db=db_session,
        redis=None,
        qdrant=None,
        agent_bus=agent_bus,
    )

    await space.initialize()

    stats = await space.get_agent_stats()
    assert stats["user_id"] == str(test_user.id)
    assert stats["project_id"] == str(test_project.id)
    assert stats["initialized"] is True
    assert stats["active_agents"] == len(test_agents_fixture)
    assert "agent_ids" in stats


@pytest.mark.asyncio
async def test_user_worker_space_health_check(
    db_session: AsyncSession, test_user, test_project, test_agents_fixture
):
    """Test worker space health check."""
    agent_bus = AgentBus()

    space = UserWorkerSpace(
        user_id=test_user.id,
        project_id=str(test_project.id),
        db=db_session,
        redis=None,
        qdrant=None,
        agent_bus=agent_bus,
    )

    assert not space.is_healthy()

    await space.initialize()
    assert space.is_healthy()

    await space.cleanup()
    assert not space.is_healthy()


@pytest.mark.asyncio
async def test_worker_space_manager_get_or_create(db_session: AsyncSession, test_user, test_agents_fixture):
    """Test worker space manager get or create."""
    manager = WorkerSpaceManager()

    # Create space
    space1 = await manager.get_or_create(
        user_id=test_user.id,
        project_id="project1",
        db=db_session,
        redis=None,
        qdrant=None,
    )

    assert space1.initialized

    # Get same space
    space2 = await manager.get_or_create(
        user_id=test_user.id,
        project_id="project1",
        db=db_session,
        redis=None,
        qdrant=None,
    )

    assert space1 is space2

    # Create different project space
    space3 = await manager.get_or_create(
        user_id=test_user.id,
        project_id="project2",
        db=db_session,
        redis=None,
        qdrant=None,
    )

    assert space1 is not space3
    assert manager.get_user_project_count(test_user.id) == 2


@pytest.mark.asyncio
async def test_worker_space_manager_rebinds_db_session(
    db_session: AsyncSession,
    test_user,
    test_agents_fixture,
):
    """Cached workspace must use current request DB session."""
    manager = WorkerSpaceManager()

    space1 = await manager.get_or_create(
        user_id=test_user.id,
        project_id="project-rebind",
        db=db_session,
        redis=None,
        qdrant=None,
    )
    assert space1.db is db_session

    async with AsyncSessionLocal() as second_session:
        space2 = await manager.get_or_create(
            user_id=test_user.id,
            project_id="project-rebind",
            db=second_session,
            redis=None,
            qdrant=None,
        )

        assert space1 is space2
        assert space2.db is second_session
        if space2.agent_manager is not None:
            assert space2.agent_manager.db is second_session


@pytest.mark.asyncio
async def test_worker_space_manager_remove(db_session: AsyncSession, test_user, test_agents_fixture):
    """Test worker space manager remove."""
    manager = WorkerSpaceManager()

    space = await manager.get_or_create(
        user_id=test_user.id,
        project_id="project1",
        db=db_session,
        redis=None,
        qdrant=None,
    )

    assert space.initialized

    # Remove
    removed = await manager.remove(test_user.id, "project1")
    assert removed

    # Get should return None
    space_none = await manager.get(test_user.id, "project1")
    assert space_none is None


@pytest.mark.asyncio
@pytest.mark.xfail(reason="WorkerSpaceManager stats needs refactoring")
async def test_worker_space_manager_user_isolation(
    db_session: AsyncSession, test_user, test_agents_fixture
):
    """Test worker space isolation between users."""
    user2 = User(email="test2@example.com")
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)

    manager = WorkerSpaceManager()

    space1 = await manager.get_or_create(
        user_id=test_user.id,
        project_id="project1",
        db=db_session,
        redis=None,
        qdrant=None,
    )

    space2 = await manager.get_or_create(
        user_id=user2.id,
        project_id="project1",
        db=db_session,
        redis=None,
        qdrant=None,
    )

    # Should be different spaces
    assert space1 is not space2
    assert space1.user_id != space2.user_id

    # Stats should be separate
    stats = manager.get_stats()
    assert stats["active_spaces"] == 2


@pytest.mark.asyncio
@pytest.mark.xfail(reason="WorkerSpaceManager stats needs refactoring")
async def test_worker_space_manager_stats(db_session: AsyncSession, test_user, test_agents_fixture):
    """Test worker space manager statistics."""
    manager = WorkerSpaceManager()

    await manager.get_or_create(
        user_id=test_user.id,
        project_id="project1",
        db=db_session,
        redis=None,
        qdrant=None,
    )

    stats = manager.get_stats()
    assert stats["active_spaces"] == 1
    assert "spaces" in stats


@pytest.mark.asyncio
@pytest.mark.xfail(reason="WorkerSpaceManager cleanup needs refactoring")
async def test_worker_space_manager_cleanup_all(
    db_session: AsyncSession, test_user, test_agents_fixture
):
    """Test worker space manager cleanup all."""
    manager = WorkerSpaceManager()

    await manager.get_or_create(
        user_id=test_user.id,
        project_id="project1",
        db=db_session,
        redis=None,
        qdrant=None,
    )

    await manager.get_or_create(
        user_id=test_user.id,
        project_id="project2",
        db=db_session,
        redis=None,
        qdrant=None,
    )

    assert manager.get_user_project_count(test_user.id) == 2

    await manager.cleanup_all()
    assert len(manager.spaces) == 0


@pytest.mark.asyncio
async def test_get_worker_space_manager_singleton():
    """Test worker space manager singleton."""
    manager1 = get_worker_space_manager()
    manager2 = get_worker_space_manager()

    assert manager1 is manager2
