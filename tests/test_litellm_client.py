"""Unit tests for LiteLLMClient."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.litellm_client import LiteLLMClient
import httpx


@pytest.fixture
def litellm_client():
    """Create LiteLLMClient instance for testing."""
    return LiteLLMClient()


@pytest.fixture
def test_user_id():
    """Generate test user ID."""
    return uuid4()


@pytest.mark.asyncio
async def test_add_model_success(litellm_client: LiteLLMClient, test_user_id):
    """Test successful model registration in LiteLLM."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        model_name = await litellm_client.add_model(
            user_id=test_user_id,
            provider_type="openai",
            api_key="sk-test123",
            config={"model": "gpt-4o"},
        )

        assert model_name is not None
        assert "user" in model_name
        assert "openai" in model_name
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_delete_model_success(litellm_client: LiteLLMClient):
    """Test successful model deletion from LiteLLM."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        await litellm_client.delete_model("user550e8400_openai_abc123")

        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_test_model_success(litellm_client: LiteLLMClient):
    """Test successful model testing."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Hello! I'm an AI assistant."
                    }
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        result = await litellm_client.test_model(
            litellm_model_name="user550e8400_openai_abc123",
            test_prompt="Hello!",
        )

        assert result["success"] is True
        assert "Hello!" in result["response"]
        assert result["latency_ms"] is not None
        assert result["error"] is None


@pytest.mark.asyncio
async def test_test_model_failure(litellm_client: LiteLLMClient):
    """Test model testing failure."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.TimeoutException("Connection timeout")
        )
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        result = await litellm_client.test_model(
            litellm_model_name="user550e8400_openai_abc123"
        )

        assert result["success"] is False
        assert result["response"] is None
        assert result["error"] is not None


@pytest.mark.asyncio
async def test_http_request_retry_on_timeout(litellm_client: LiteLLMClient):
    """Test HTTP request retry logic on timeout."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        # First attempt fails with timeout, second succeeds
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()
        
        mock_client.post = AsyncMock(
            side_effect=[
                httpx.TimeoutException("Timeout"),
                mock_response
            ]
        )
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        result = await litellm_client._http_request(
            method="POST",
            endpoint="/test",
            payload={"test": "data"}
        )

        assert result["success"] is True
        assert mock_client.post.call_count == 2  # Should retry


@pytest.mark.asyncio
async def test_http_request_no_retry_on_http_error(litellm_client: LiteLLMClient):
    """Test HTTP request does not retry on HTTP status errors."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        error = httpx.HTTPStatusError("401 Unauthorized", request=MagicMock(), response=mock_response)
        
        mock_client.post = AsyncMock(side_effect=error)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await litellm_client._http_request(
                method="POST",
                endpoint="/test",
                payload={"test": "data"}
            )

        assert mock_client.post.call_count == 1  # Should not retry


def test_generate_litellm_model_name(litellm_client: LiteLLMClient, test_user_id):
    """Test model name generation."""
    name = litellm_client._generate_litellm_model_name(test_user_id, "openai")
    
    assert name.startswith("user")
    assert "openai" in name
    assert "_" in name
    # Should have format: user<id>_openai_<random>
    parts = name.split("_")
    assert len(parts) == 3
    assert parts[0].startswith("user")
    assert parts[1] == "openai"
    assert len(parts[2]) == 8  # random suffix


def test_generate_litellm_model_name_different_providers(litellm_client: LiteLLMClient, test_user_id):
    """Test model name generation for different providers."""
    providers = ["openai", "anthropic", "google", "cohere"]
    
    for provider in providers:
        name = litellm_client._generate_litellm_model_name(test_user_id, provider)
        assert provider in name


def test_build_model_id(litellm_client: LiteLLMClient):
    """Test model ID building."""
    model_id = litellm_client._build_model_id("openai", "user550e8400_openai_abc123")
    
    assert model_id == "openai/user550e8400_openai_abc123"


@pytest.mark.asyncio
async def test_add_model_with_config(litellm_client: LiteLLMClient, test_user_id):
    """Test adding model with custom configuration."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        config = {
            "model": "gpt-4-turbo",
            "max_tokens": 4096,
            "temperature": 0.5,
        }
        
        model_name = await litellm_client.add_model(
            user_id=test_user_id,
            provider_type="openai",
            api_key="sk-test",
            config=config,
        )

        # Verify the request included the config
        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["model"] == "gpt-4-turbo"
        assert payload["max_tokens"] == 4096
        assert payload["temperature"] == 0.5


def test_litellm_client_initialization():
    """Test LiteLLMClient initialization."""
    client = LiteLLMClient()
    
    assert client.base_url is not None
    assert client.master_key is not None
    assert client.timeout == 60.0
    assert client.max_retries == 3
    assert client.retry_delay == 1.0
