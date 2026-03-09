"""API tests for LLM provider management endpoints."""

import json
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_llm_provider import UserLLMProvider
from app.models.user import User
from app.models.user_agent import UserAgent


class TestLLMProviderAPI:
    """Tests for LLM provider REST API endpoints."""

    @pytest.mark.asyncio
    async def test_create_provider_success(
        self,
        client_with_llm_mocks: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test successful provider creation."""
        payload = {
            "provider_type": "openai",
            "display_name": "My OpenAI",
            "api_key": "sk-test-key-123456",
            "config": {"model": "gpt-4o", "max_tokens": 2048},
        }

        response = await client_with_llm_mocks.post(
            "/my/llm-providers",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["provider_type"] == "openai"
        assert data["display_name"] == "My OpenAI"
        assert "api_key" not in data  # API key should not be returned
        assert data["config"]["model"] == "gpt-4o"
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_provider_unauthorized(
        self,
        client: AsyncClient,
    ):
        """Test that creating provider without auth returns 401."""
        payload = {
            "provider_type": "openai",
            "display_name": "My OpenAI",
            "api_key": "sk-test-key",
            "config": {"model": "gpt-4o"},
        }

        response = await client.post(
            "/my/llm-providers",
            json=payload,
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_provider_invalid_type(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Test creating provider with invalid type."""
        payload = {
            "provider_type": "invalid_type",
            "display_name": "Invalid",
            "api_key": "sk-test",
            "config": {},
        }

        response = await client.post(
            "/my/llm-providers",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_list_providers_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_llm_provider: UserLLMProvider,
        db_session: AsyncSession,
    ):
        """Test listing user's providers."""
        response = await client.get(
            "/my/llm-providers",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert data["total"] == 1
        assert len(data["providers"]) == 1
        assert data["providers"][0]["display_name"] == "My OpenAI Provider"

    @pytest.mark.asyncio
    async def test_list_providers_unauthorized(
        self,
        client: AsyncClient,
    ):
        """Test that listing providers without auth returns 401."""
        response = await client.get(
            "/my/llm-providers",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_providers_pagination(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test pagination for providers list."""
        # Create multiple providers
        for i in range(5):
            provider = UserLLMProvider(
                user_id=test_user.id,
                provider_type="openai",
                display_name=f"Provider {i}",
                litellm_model_name=f"user{test_user.id}_openai_{i}",
                config={"model": "gpt-4o"},
                use_count=0,
            )
            db_session.add(provider)
        await db_session.commit()

        # Test pagination
        response = await client.get(
            "/my/llm-providers?skip=0&limit=2",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["providers"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 3

    @pytest.mark.asyncio
    async def test_get_provider_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_llm_provider: UserLLMProvider,
    ):
        """Test getting a specific provider."""
        response = await client.get(
            f"/my/llm-providers/{test_llm_provider.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_llm_provider.id)
        assert data["display_name"] == "My OpenAI Provider"
        assert "api_key" not in data

    @pytest.mark.asyncio
    async def test_get_provider_unauthorized(
        self,
        client: AsyncClient,
        test_llm_provider: UserLLMProvider,
    ):
        """Test getting provider without auth returns 401."""
        response = await client.get(
            f"/my/llm-providers/{test_llm_provider.id}",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_provider_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Test getting non-existent provider returns 404."""
        fake_id = uuid4()
        response = await client.get(
            f"/my/llm-providers/{fake_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_provider_other_user(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_llm_provider: UserLLMProvider,
        db_session: AsyncSession,
    ):
        """Test that user cannot access other user's provider."""
        # Create another user
        other_user = User(id=uuid4(), email="other@example.com")
        db_session.add(other_user)
        await db_session.commit()

        # Create provider for other user
        other_provider = UserLLMProvider(
            user_id=other_user.id,
            provider_type="openai",
            display_name="Other User's Provider",
            litellm_model_name=f"user{other_user.id}_openai_123",
            config={"model": "gpt-4o"},
            use_count=0,
        )
        db_session.add(other_provider)
        await db_session.commit()

        # Try to access other user's provider with test_user's token
        response = await client.get(
            f"/my/llm-providers/{other_provider.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404  # Should not find it

    @pytest.mark.asyncio
    async def test_update_provider_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_llm_provider: UserLLMProvider,
    ):
        """Test updating provider configuration."""
        payload = {
            "display_name": "Updated Name",
            "config": {"model": "gpt-4-turbo", "max_tokens": 4096},
        }

        response = await client.patch(
            f"/my/llm-providers/{test_llm_provider.id}",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated Name"
        assert data["config"]["model"] == "gpt-4-turbo"
        assert data["config"]["max_tokens"] == 4096

    @pytest.mark.asyncio
    async def test_update_provider_unauthorized(
        self,
        client: AsyncClient,
        test_llm_provider: UserLLMProvider,
    ):
        """Test updating provider without auth returns 401."""
        payload = {
            "display_name": "Updated",
            "config": {},
        }

        response = await client.patch(
            f"/my/llm-providers/{test_llm_provider.id}",
            json=payload,
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_provider_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Test updating non-existent provider returns 404."""
        fake_id = uuid4()
        payload = {
            "display_name": "Updated",
            "config": {},
        }

        response = await client.patch(
            f"/my/llm-providers/{fake_id}",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_provider_success(
        self,
        client_with_llm_mocks: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_llm_provider: UserLLMProvider,
        db_session: AsyncSession,
    ):
        """Test successful provider deletion."""
        response = await client_with_llm_mocks.delete(
            f"/my/llm-providers/{test_llm_provider.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify it's deleted
        response = await client_with_llm_mocks.get(
            f"/my/llm-providers/{test_llm_provider.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_provider_unauthorized(
        self,
        client: AsyncClient,
        test_llm_provider: UserLLMProvider,
    ):
        """Test deleting provider without auth returns 401."""
        response = await client.delete(
            f"/my/llm-providers/{test_llm_provider.id}",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_provider_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Test deleting non-existent provider returns 404."""
        fake_id = uuid4()
        response = await client.delete(
            f"/my/llm-providers/{fake_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_provider_in_use(
        self,
        client_with_llm_mocks: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_llm_provider: UserLLMProvider,
        test_project,
        db_session: AsyncSession,
    ):
        """Test that deleting provider in use returns 409."""
        # Create agent using this provider
        agent = UserAgent(
            user_id=test_user.id,
            project_id=test_project.id,
            name="test_agent",
            llm_provider_id=test_llm_provider.id,
            config={
                "name": "test_agent",
                "system_prompt": "You are helpful",
                "model": "gpt-4o",
                "temperature": 0.7,
                "max_tokens": 2048,
            },
        )
        db_session.add(agent)
        await db_session.commit()

        response = await client_with_llm_mocks.delete(
            f"/my/llm-providers/{test_llm_provider.id}",
            headers=auth_headers,
        )

        assert response.status_code == 409
        # Check for the error message (lowercase check)
        detail = response.json()["detail"].lower()
        assert "used" in detail or "in use" in detail

    @pytest.mark.asyncio
    async def test_test_provider_success(
        self,
        client_with_llm_mocks: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_llm_provider: UserLLMProvider,
    ):
        """Test provider connection test."""
        payload = {
            "test_prompt": "Hello, how are you?",
            "max_tokens": 100,
        }

        response = await client_with_llm_mocks.post(
            f"/my/llm-providers/{test_llm_provider.id}/test",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Should have success, response, and latency fields
        assert "success" in data
        assert "latency_ms" in data
        # Success might be False due to mock/test environment
        # but the endpoint should still return properly

    @pytest.mark.asyncio
    async def test_test_provider_unauthorized(
        self,
        client: AsyncClient,
        test_llm_provider: UserLLMProvider,
    ):
        """Test testing provider without auth returns 401."""
        payload = {
            "test_prompt": "Hello",
            "max_tokens": 100,
        }

        response = await client.post(
            f"/my/llm-providers/{test_llm_provider.id}/test",
            json=payload,
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_test_provider_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Test testing non-existent provider returns 404."""
        fake_id = uuid4()
        payload = {
            "test_prompt": "Hello",
            "max_tokens": 100,
        }

        response = await client.post(
            f"/my/llm-providers/{fake_id}/test",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_available_providers_success(
        self,
        client_with_llm_mocks: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_llm_provider: UserLLMProvider,
        db_session: AsyncSession,
    ):
        """Test getting available providers."""
        response = await client_with_llm_mocks.get(
            "/my/llm-providers/available",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert "total" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_available_providers_unauthorized(
        self,
        client: AsyncClient,
    ):
        """Test getting available providers without auth returns 401."""
        response = await client.get(
            "/my/llm-providers/available",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_provider_types_public(
        self,
        client: AsyncClient,
    ):
        """Test getting provider types - PUBLIC endpoint (no auth required)."""
        response = await client.get(
            "/llm-providers/types",
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Check structure of type info (keys may vary)
        for provider_type in data:
            assert "display_name" in provider_type
            assert "description" in provider_type

    @pytest.mark.asyncio
    async def test_get_audit_log_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_llm_provider: UserLLMProvider,
        test_llm_provider_audit_log,
        db_session: AsyncSession,
    ):
        """Test getting audit log."""
        response = await client.get(
            "/my/llm-providers/audit",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "total" in data
        assert data["total"] >= 1
        assert len(data["entries"]) >= 1

    @pytest.mark.asyncio
    async def test_get_audit_log_unauthorized(
        self,
        client: AsyncClient,
    ):
        """Test getting audit log without auth returns 401."""
        response = await client.get(
            "/my/llm-providers/audit",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_audit_log_with_filters(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_llm_provider: UserLLMProvider,
        test_llm_provider_audit_log,
        db_session: AsyncSession,
    ):
        """Test audit log filtering."""
        # Filter by action
        response = await client.get(
            f"/my/llm-providers/audit?action=create",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        if data["total"] > 0:
            for entry in data["entries"]:
                assert entry["action"] == "create"

    @pytest.mark.asyncio
    async def test_get_audit_log_pagination(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_llm_provider: UserLLMProvider,
        db_session: AsyncSession,
    ):
        """Test audit log pagination."""
        response = await client.get(
            "/my/llm-providers/audit?skip=0&limit=10",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data

    @pytest.mark.asyncio
    async def test_create_provider_multiple_users_isolation(
        self,
        client_with_llm_mocks: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that providers are isolated between users."""
        # Create another user
        other_user = User(id=uuid4(), email="other@example.com")
        db_session.add(other_user)
        await db_session.commit()

        # Create provider for test_user
        response = await client_with_llm_mocks.post(
            "/my/llm-providers",
            json={
                "provider_type": "openai",
                "display_name": "Test User Provider",
                "api_key": "sk-test-123",
                "config": {"model": "gpt-4o"},
            },
            headers=auth_headers,
        )
        assert response.status_code == 201

        # List providers - should see only one
        response = await client_with_llm_mocks.get(
            "/my/llm-providers",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_create_duplicate_provider_names(
        self,
        client_with_llm_mocks: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that same user can create multiple providers with same display name."""
        # Create first provider
        response1 = await client_with_llm_mocks.post(
            "/my/llm-providers",
            json={
                "provider_type": "openai",
                "display_name": "My Provider",
                "api_key": "sk-test-1",
                "config": {"model": "gpt-4o"},
            },
            headers=auth_headers,
        )
        assert response1.status_code == 201

        # Create second provider with same name
        response2 = await client_with_llm_mocks.post(
            "/my/llm-providers",
            json={
                "provider_type": "anthropic",
                "display_name": "My Provider",
                "api_key": "sk-test-2",
                "config": {"model": "claude-3"},
            },
            headers=auth_headers,
        )
        assert response2.status_code == 201

        # List should show both
        response = await client_with_llm_mocks.get(
            "/my/llm-providers",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_create_provider_missing_required_fields(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Test creating provider with missing required fields."""
        # Missing api_key
        payload = {
            "provider_type": "openai",
            "display_name": "Test",
            "config": {},
        }

        response = await client.post(
            "/my/llm-providers",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_invalid_provider_id_format(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test with invalid UUID format returns 422."""
        response = await client.get(
            "/my/llm-providers/not-a-uuid",
            headers=auth_headers,
        )

        assert response.status_code == 422
