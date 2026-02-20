"""Test AgentBus cleanup functionality."""

import asyncio
from uuid import uuid4

import pytest

from app.core.agent_bus import AgentBus, TaskItem


@pytest.mark.asyncio
async def test_agent_bus_cleanup():
    """Test that AgentBus cleanup method works correctly."""
    bus = AgentBus()
    
    # Register a test agent
    agent_id = uuid4()
    
    async def test_handler(task_item: TaskItem):
        """Simple test handler."""
        await asyncio.sleep(0.1)
        return {"status": "completed"}
    
    await bus.register_agent(agent_id, test_handler, max_concurrency=2)
    
    # Verify agent is registered
    assert agent_id in bus.queues
    assert agent_id in bus.workers
    assert agent_id in bus.agent_handlers
    assert agent_id in bus.max_concurrency
    assert agent_id in bus.active_tasks
    
    # Submit a task
    task_item = await bus.submit_task(
        agent_id=agent_id,
        task_id="test-task-1",
        payload={"test": "data"},
    )
    
    # Wait a bit for task to start processing
    await asyncio.sleep(0.05)
    
    # Cleanup
    await bus.cleanup()
    
    # Verify everything is cleaned up
    assert len(bus.queues) == 0
    assert len(bus.workers) == 0
    assert len(bus.agent_handlers) == 0
    assert len(bus.max_concurrency) == 0
    assert len(bus.active_tasks) == 0


@pytest.mark.asyncio
async def test_agent_bus_cleanup_multiple_agents():
    """Test cleanup with multiple agents."""
    bus = AgentBus()
    
    async def test_handler(task_item: TaskItem):
        """Simple test handler."""
        return {"status": "completed"}
    
    # Register multiple agents
    agent_ids = [uuid4() for _ in range(3)]
    for agent_id in agent_ids:
        await bus.register_agent(agent_id, test_handler)
    
    # Verify all agents are registered
    assert len(bus.queues) == 3
    assert len(bus.workers) == 3
    
    # Cleanup
    await bus.cleanup()
    
    # Verify everything is cleaned up
    assert len(bus.queues) == 0
    assert len(bus.workers) == 0
    assert len(bus.agent_handlers) == 0
    assert len(bus.max_concurrency) == 0
    assert len(bus.active_tasks) == 0


@pytest.mark.asyncio
async def test_agent_bus_cleanup_empty():
    """Test cleanup on empty bus."""
    bus = AgentBus()
    
    # Cleanup empty bus should not raise errors
    await bus.cleanup()
    
    # Verify everything is still empty
    assert len(bus.queues) == 0
    assert len(bus.workers) == 0
    assert len(bus.agent_handlers) == 0
    assert len(bus.max_concurrency) == 0
    assert len(bus.active_tasks) == 0
