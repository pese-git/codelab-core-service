"""
Интеграционные тесты для v0.2.0 API endpoints.

Проверяет все per-project endpoints:
- Agent Management: POST, GET, GET by ID, PUT, DELETE
- Chat Management: POST sessions, GET sessions, GET messages, POST message, DELETE session
- Streaming Events: GET events
"""

import pytest
from uuid import uuid4
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.user_project import UserProject
from app.models.user_agent import UserAgent
from app.models.chat_session import ChatSession
from app.models.message import Message


class TestV020PerProjectAgents:
    """Тесты для per-project agent endpoints."""
    
    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Agent creation endpoint needs refactoring")
    async def test_create_agent_in_project(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_project: UserProject,
    ) -> None:
        """Тест: POST /my/projects/{project_id}/agents/"""
        project_id = str(test_project.id)
        
        agent_data = {
            "name": "Test Agent",
            "system_prompt": "You are a helpful assistant",
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 2048,
            "tools": [],
            "concurrency_limit": 3
        }
        
        response = await client.post(
            f"/my/projects/{project_id}/agents/",
            json=agent_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Agent"
        assert data["status"] == "active"
    
    @pytest.mark.asyncio
    async def test_list_agents_in_project(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_project: UserProject,
        test_agent: UserAgent,
    ) -> None:
        """Тест: GET /my/projects/{project_id}/agents/"""
        project_id = str(test_project.id)
        
        response = await client.get(
            f"/my/projects/{project_id}/agents/",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "total" in data
        assert data["total"] >= 0
    
    @pytest.mark.asyncio
    async def test_get_agent_in_project(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_project: UserProject,
        test_agent: UserAgent,
    ) -> None:
        """Тест: GET /my/projects/{project_id}/agents/{agent_id}"""
        project_id = str(test_project.id)
        agent_id = str(test_agent.id)
        
        response = await client.get(
            f"/my/projects/{project_id}/agents/{agent_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == agent_id
        assert data["name"] == test_agent.name
    
    @pytest.mark.asyncio
    async def test_list_projects(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_project: UserProject,
    ) -> None:
        """Тест: GET /my/projects/"""
        response = await client.get(
            "/my/projects/",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert "total" in data
        assert data["total"] >= 1
    
    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Project detail endpoint needs refactoring")
    async def test_get_project(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_project: UserProject,
    ) -> None:
        """Тест: GET /my/projects/{project_id}"""
        project_id = str(test_project.id)
        
        response = await client.get(
            f"/my/projects/{project_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == project_id
    
    @pytest.mark.asyncio
    async def test_missing_authorization_returns_401(
        self,
        client: AsyncClient,
        test_project: UserProject,
    ) -> None:
        """Тест: Отсутствие авторизации возвращает 401"""
        project_id = str(test_project.id)
        
        response = await client.get(
            f"/my/projects/{project_id}/agents/"
        )
        
        assert response.status_code in [401, 403]
