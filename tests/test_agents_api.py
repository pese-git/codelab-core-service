"""Tests for agents API endpoints."""

import pytest
from uuid import UUID, uuid4
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.user_agent import UserAgent


class TestCreateAgent:
    """Tests for POST /my/agents/."""

    @pytest.mark.asyncio
    async def test_create_agent_success(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test successful agent creation."""
        agent_data = {
            "name": "test_coder",
            "system_prompt": "You are an expert Python developer",
            "model": "gpt-4-turbo-preview",
            "tools": ["code_executor", "file_reader"],
            "concurrency_limit": 3,
            "temperature": 0.7,
            "max_tokens": 4096,
            "metadata": {"specialty": "backend"},
        }

        response = await client_with_mocks.post(
            "/my/agents/",
            json=agent_data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test_coder"
        assert data["status"] == "ready"
        assert "id" in data
        assert "created_at" in data
        assert data["config"]["system_prompt"] == agent_data["system_prompt"]
        assert data["config"]["model"] == agent_data["model"]
        assert data["config"]["tools"] == agent_data["tools"]

    @pytest.mark.asyncio
    async def test_create_agent_minimal_config(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test agent creation with minimal configuration."""
        agent_data = {
            "name": "minimal_agent",
            "system_prompt": "You are a helpful assistant",
        }

        response = await client_with_mocks.post(
            "/my/agents/",
            json=agent_data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "minimal_agent"
        assert data["config"]["model"] == "gpt-4-turbo-preview"  # default
        assert data["config"]["tools"] == []  # default
        assert data["config"]["concurrency_limit"] == 3  # default

    @pytest.mark.asyncio
    async def test_create_agent_invalid_name(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test agent creation with invalid name."""
        agent_data = {
            "name": "",  # empty name
            "system_prompt": "You are a helpful assistant",
        }

        response = await client_with_mocks.post(
            "/my/agents/",
            json=agent_data,
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_agent_invalid_temperature(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test agent creation with invalid temperature."""
        agent_data = {
            "name": "test_agent",
            "system_prompt": "You are a helpful assistant",
            "temperature": 3.0,  # out of range
        }

        response = await client_with_mocks.post(
            "/my/agents/",
            json=agent_data,
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_agent_invalid_concurrency(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test agent creation with invalid concurrency limit."""
        agent_data = {
            "name": "test_agent",
            "system_prompt": "You are a helpful assistant",
            "concurrency_limit": 15,  # exceeds max
        }

        response = await client_with_mocks.post(
            "/my/agents/",
            json=agent_data,
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_agent_unauthorized(
        self,
        client_with_mocks: AsyncClient,
    ):
        """Test agent creation without authentication."""
        agent_data = {
            "name": "test_agent",
            "system_prompt": "You are a helpful assistant",
        }

        response = await client_with_mocks.post(
            "/my/agents/",
            json=agent_data,
        )

        assert response.status_code == 401


class TestListAgents:
    """Tests for GET /my/agents/."""

    @pytest.mark.asyncio
    async def test_list_agents_empty(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test listing agents when none exist."""
        response = await client_with_mocks.get(
            "/my/agents/",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agents"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_agents_with_data(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
        db_session: AsyncSession,
    ):
        """Test listing agents with existing data."""
        # Create test agents
        agent1 = UserAgent(
            user_id=test_user.id,
            name="agent1",
            config={
                "system_prompt": "Prompt 1",
                "model": "gpt-4-turbo-preview",
                "tools": [],
                "concurrency_limit": 3,
                "temperature": 0.7,
                "max_tokens": 4096,
                "metadata": {},
            },
            status="ready",
        )
        agent2 = UserAgent(
            user_id=test_user.id,
            name="agent2",
            config={
                "system_prompt": "Prompt 2",
                "model": "gpt-4-turbo-preview",
                "tools": ["tool1"],
                "concurrency_limit": 5,
                "temperature": 0.5,
                "max_tokens": 2048,
                "metadata": {},
            },
            status="busy",
        )
        db_session.add_all([agent1, agent2])
        await db_session.commit()

        response = await client_with_mocks.get(
            "/my/agents/",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["agents"]) == 2
        
        agent_names = {agent["name"] for agent in data["agents"]}
        assert agent_names == {"agent1", "agent2"}

    @pytest.mark.asyncio
    async def test_list_agents_user_isolation(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
        db_session: AsyncSession,
    ):
        """Test that users only see their own agents."""
        # Create another user
        other_user = User(
            id=uuid4(),
            email="other@example.com",
        )
        db_session.add(other_user)
        await db_session.commit()

        # Create agents for both users
        my_agent = UserAgent(
            user_id=test_user.id,
            name="my_agent",
            config={
                "system_prompt": "My prompt",
                "model": "gpt-4-turbo-preview",
                "tools": [],
                "concurrency_limit": 3,
                "temperature": 0.7,
                "max_tokens": 4096,
                "metadata": {},
            },
        )
        other_agent = UserAgent(
            user_id=other_user.id,
            name="other_agent",
            config={
                "system_prompt": "Other prompt",
                "model": "gpt-4-turbo-preview",
                "tools": [],
                "concurrency_limit": 3,
                "temperature": 0.7,
                "max_tokens": 4096,
                "metadata": {},
            },
        )
        db_session.add_all([my_agent, other_agent])
        await db_session.commit()

        response = await client_with_mocks.get(
            "/my/agents/",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["agents"][0]["name"] == "my_agent"

    @pytest.mark.asyncio
    async def test_list_agents_unauthorized(
        self,
        client_with_mocks: AsyncClient,
    ):
        """Test listing agents without authentication."""
        response = await client_with_mocks.get("/my/agents/")
        assert response.status_code == 401


class TestGetAgent:
    """Tests for GET /my/agents/{agent_id}."""

    @pytest.mark.asyncio
    async def test_get_agent_success(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
        db_session: AsyncSession,
    ):
        """Test getting agent by ID."""
        agent = UserAgent(
            user_id=test_user.id,
            name="test_agent",
            config={
                "system_prompt": "Test prompt",
                "model": "gpt-4-turbo-preview",
                "tools": ["tool1", "tool2"],
                "concurrency_limit": 3,
                "temperature": 0.7,
                "max_tokens": 4096,
                "metadata": {"key": "value"},
            },
            status="ready",
        )
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        response = await client_with_mocks.get(
            f"/my/agents/{agent.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(agent.id)
        assert data["name"] == "test_agent"
        assert data["status"] == "ready"
        assert data["config"]["system_prompt"] == "Test prompt"
        assert data["config"]["tools"] == ["tool1", "tool2"]
        assert data["config"]["metadata"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_agent_not_found(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test getting non-existent agent."""
        fake_id = uuid4()
        response = await client_with_mocks.get(
            f"/my/agents/{fake_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Agent not found"

    @pytest.mark.asyncio
    async def test_get_agent_wrong_user(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
        db_session: AsyncSession,
    ):
        """Test getting agent belonging to another user."""
        # Create another user and their agent
        other_user = User(
            id=uuid4(),
            email="other@example.com",
        )
        db_session.add(other_user)
        await db_session.commit()

        other_agent = UserAgent(
            user_id=other_user.id,
            name="other_agent",
            config={
                "system_prompt": "Other prompt",
                "model": "gpt-4-turbo-preview",
                "tools": [],
                "concurrency_limit": 3,
                "temperature": 0.7,
                "max_tokens": 4096,
                "metadata": {},
            },
        )
        db_session.add(other_agent)
        await db_session.commit()
        await db_session.refresh(other_agent)

        response = await client_with_mocks.get(
            f"/my/agents/{other_agent.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_agent_invalid_uuid(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test getting agent with invalid UUID."""
        response = await client_with_mocks.get(
            "/my/agents/invalid-uuid",
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_agent_unauthorized(
        self,
        client_with_mocks: AsyncClient,
    ):
        """Test getting agent without authentication."""
        fake_id = uuid4()
        response = await client_with_mocks.get(f"/my/agents/{fake_id}")
        assert response.status_code == 401


class TestUpdateAgent:
    """Tests for PUT /my/agents/{agent_id}."""

    @pytest.mark.asyncio
    async def test_update_agent_success(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
        db_session: AsyncSession,
    ):
        """Test successful agent update."""
        agent = UserAgent(
            user_id=test_user.id,
            name="old_name",
            config={
                "system_prompt": "Old prompt",
                "model": "gpt-4-turbo-preview",
                "tools": [],
                "concurrency_limit": 3,
                "temperature": 0.7,
                "max_tokens": 4096,
                "metadata": {},
            },
        )
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        update_data = {
            "config": {
                "name": "new_name",
                "system_prompt": "New prompt",
                "model": "gpt-4o",
                "tools": ["new_tool"],
                "concurrency_limit": 5,
                "temperature": 0.9,
                "max_tokens": 8192,
                "metadata": {"updated": True},
            }
        }

        response = await client_with_mocks.put(
            f"/my/agents/{agent.id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "new_name"
        assert data["config"]["system_prompt"] == "New prompt"
        assert data["config"]["model"] == "gpt-4o"
        assert data["config"]["tools"] == ["new_tool"]
        assert data["config"]["concurrency_limit"] == 5
        assert data["config"]["temperature"] == 0.9

    @pytest.mark.asyncio
    async def test_update_agent_not_found(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test updating non-existent agent."""
        fake_id = uuid4()
        update_data = {
            "config": {
                "name": "test",
                "system_prompt": "Test prompt",
            }
        }

        response = await client_with_mocks.put(
            f"/my/agents/{fake_id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_agent_wrong_user(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
        db_session: AsyncSession,
    ):
        """Test updating agent belonging to another user."""
        other_user = User(
            id=uuid4(),
            email="other@example.com",
        )
        db_session.add(other_user)
        await db_session.commit()

        other_agent = UserAgent(
            user_id=other_user.id,
            name="other_agent",
            config={
                "system_prompt": "Other prompt",
                "model": "gpt-4-turbo-preview",
                "tools": [],
                "concurrency_limit": 3,
                "temperature": 0.7,
                "max_tokens": 4096,
                "metadata": {},
            },
        )
        db_session.add(other_agent)
        await db_session.commit()
        await db_session.refresh(other_agent)

        update_data = {
            "config": {
                "name": "hacked",
                "system_prompt": "Hacked prompt",
            }
        }

        response = await client_with_mocks.put(
            f"/my/agents/{other_agent.id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_agent_invalid_config(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
        db_session: AsyncSession,
    ):
        """Test updating agent with invalid configuration."""
        agent = UserAgent(
            user_id=test_user.id,
            name="test_agent",
            config={
                "system_prompt": "Test prompt",
                "model": "gpt-4-turbo-preview",
                "tools": [],
                "concurrency_limit": 3,
                "temperature": 0.7,
                "max_tokens": 4096,
                "metadata": {},
            },
        )
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        update_data = {
            "config": {
                "name": "test",
                "system_prompt": "Test",
                "temperature": 5.0,  # invalid
            }
        }

        response = await client_with_mocks.put(
            f"/my/agents/{agent.id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_agent_unauthorized(
        self,
        client_with_mocks: AsyncClient,
    ):
        """Test updating agent without authentication."""
        fake_id = uuid4()
        update_data = {
            "config": {
                "name": "test",
                "system_prompt": "Test prompt",
            }
        }

        response = await client_with_mocks.put(
            f"/my/agents/{fake_id}",
            json=update_data,
        )

        assert response.status_code == 401


class TestDeleteAgent:
    """Tests for DELETE /my/agents/{agent_id}."""

    @pytest.mark.asyncio
    async def test_delete_agent_success(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
        db_session: AsyncSession,
    ):
        """Test successful agent deletion."""
        agent = UserAgent(
            user_id=test_user.id,
            name="test_agent",
            config={
                "system_prompt": "Test prompt",
                "model": "gpt-4-turbo-preview",
                "tools": [],
                "concurrency_limit": 3,
                "temperature": 0.7,
                "max_tokens": 4096,
                "metadata": {},
            },
        )
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        response = await client_with_mocks.delete(
            f"/my/agents/{agent.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify agent is deleted
        from sqlalchemy import select
        result = await db_session.execute(
            select(UserAgent).where(UserAgent.id == agent.id)
        )
        deleted_agent = result.scalar_one_or_none()
        assert deleted_agent is None

    @pytest.mark.asyncio
    async def test_delete_agent_not_found(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test deleting non-existent agent."""
        fake_id = uuid4()
        response = await client_with_mocks.delete(
            f"/my/agents/{fake_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_agent_wrong_user(
        self,
        client_with_mocks: AsyncClient,
        test_user: User,
        auth_headers: dict,
        db_session: AsyncSession,
    ):
        """Test deleting agent belonging to another user."""
        other_user = User(
            id=uuid4(),
            email="other@example.com",
        )
        db_session.add(other_user)
        await db_session.commit()

        other_agent = UserAgent(
            user_id=other_user.id,
            name="other_agent",
            config={
                "system_prompt": "Other prompt",
                "model": "gpt-4-turbo-preview",
                "tools": [],
                "concurrency_limit": 3,
                "temperature": 0.7,
                "max_tokens": 4096,
                "metadata": {},
            },
        )
        db_session.add(other_agent)
        await db_session.commit()
        await db_session.refresh(other_agent)

        response = await client_with_mocks.delete(
            f"/my/agents/{other_agent.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

        # Verify agent still exists
        from sqlalchemy import select
        result = await db_session.execute(
            select(UserAgent).where(UserAgent.id == other_agent.id)
        )
        existing_agent = result.scalar_one_or_none()
        assert existing_agent is not None

    @pytest.mark.asyncio
    async def test_delete_agent_unauthorized(
        self,
        client_with_mocks: AsyncClient,
    ):
        """Test deleting agent without authentication."""
        fake_id = uuid4()
        response = await client_with_mocks.delete(f"/my/agents/{fake_id}")
        assert response.status_code == 401
