"""Тесты для интеграции Langfuse в AgentContextStore."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.vectorstore.agent_context_store import AgentContextStore


class TestAgentContextStoreLangfuseIntegration:
    """Тесты для трейсинга встраиваний в AgentContextStore."""

    @pytest.fixture
    def mock_qdrant_client(self):
        """Mock Qdrant client."""
        return MagicMock()

    @pytest.fixture
    def user_id(self):
        """User ID."""
        return uuid4()

    @pytest.fixture
    def context_store(self, mock_qdrant_client, user_id):
        """Create AgentContextStore with mocked dependencies."""
        with patch("app.vectorstore.agent_context_store.get_langfuse") as mock_langfuse:
            mock_langfuse_instance = MagicMock()
            mock_langfuse_instance.enabled = True
            mock_langfuse.return_value = mock_langfuse_instance
            
            store = AgentContextStore(
                client=mock_qdrant_client,
                user_id=user_id,
                agent_name="test_agent",
            )
            store.langfuse = mock_langfuse_instance
            return store

    @pytest.mark.asyncio
    async def test_set_langfuse_trace(self, context_store):
        """Тест установки Langfuse trace."""
        from app.services.langfuse_integration import LangfuseTraceRef
        
        trace = LangfuseTraceRef(id="test-trace-id")
        context_store.set_langfuse_trace(trace)
        
        assert context_store.langfuse_trace == trace

    @pytest.mark.asyncio
    async def test_create_embedding_for_interaction_with_trace(self, context_store):
        """Тест создания embedding для interaction с трейсингом."""
        from app.services.langfuse_integration import LangfuseTraceRef
        
        # Setup
        trace = LangfuseTraceRef(id="test-trace-id")
        context_store.set_langfuse_trace(trace)
        
        # Mock OpenAI embeddings
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        context_store.openai_client.embeddings.create = AsyncMock(return_value=mock_response)
        
        # Call
        embedding = await context_store._create_embedding_for_interaction(
            content="test content",
            langfuse_trace=trace,
        )
        
        # Verify
        assert embedding == [0.1, 0.2, 0.3]
        context_store.openai_client.embeddings.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_embedding_for_search_with_trace(self, context_store):
        """Тест создания embedding для search с трейсингом."""
        from app.services.langfuse_integration import LangfuseTraceRef
        
        # Setup
        trace = LangfuseTraceRef(id="test-trace-id")
        context_store.set_langfuse_trace(trace)
        
        # Mock OpenAI embeddings
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.4, 0.5, 0.6])]
        context_store.openai_client.embeddings.create = AsyncMock(return_value=mock_response)
        
        # Call
        embedding = await context_store._create_embedding_for_search(
            query="test query",
            langfuse_trace=trace,
        )
        
        # Verify
        assert embedding == [0.4, 0.5, 0.6]
        context_store.openai_client.embeddings.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_interaction_uses_traced_embedding(self, context_store):
        """Тест что add_interaction использует трейсированное создание embedding."""
        from app.services.langfuse_integration import LangfuseTraceRef
        
        # Setup
        trace = LangfuseTraceRef(id="test-trace-id")
        context_store.set_langfuse_trace(trace)
        
        # Mock methods
        context_store._ensure_collection_exists = AsyncMock(return_value=True)
        context_store.client.upsert = AsyncMock()
        
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        context_store.openai_client.embeddings.create = AsyncMock(return_value=mock_response)
        
        # Call
        point_id = await context_store.add_interaction(
            content="test content",
            interaction_type="user_message",
        )
        
        # Verify that embedding was created and upsert was called
        assert point_id != ""
        context_store.openai_client.embeddings.create.assert_called_once()
        context_store.client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_uses_traced_embedding(self, context_store):
        """Тест что search использует трейсированное создание embedding."""
        from app.services.langfuse_integration import LangfuseTraceRef
        
        # Setup
        trace = LangfuseTraceRef(id="test-trace-id")
        context_store.set_langfuse_trace(trace)
        
        # Mock methods
        context_store._ensure_collection_exists = AsyncMock(return_value=True)
        
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.2] * 1536)]
        context_store.openai_client.embeddings.create = AsyncMock(return_value=mock_response)
        
        # Mock query_points
        mock_result = MagicMock()
        mock_result.points = []
        context_store.client.query_points = AsyncMock(return_value=mock_result)
        
        # Call
        results = await context_store.search(query="test query")
        
        # Verify
        assert results == []
        context_store.openai_client.embeddings.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_embedding_with_no_trace_still_works(self, context_store):
        """Тест что embedding работает без trace (graceful degradation)."""
        # Setup without setting trace
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        context_store.openai_client.embeddings.create = AsyncMock(return_value=mock_response)
        
        # Call без trace - должно работать нормально
        embedding = await context_store._create_embedding_for_interaction(
            content="test content",
            langfuse_trace=None,
        )
        
        # Verify
        assert embedding == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_langfuse_disabled_context_store(self):
        """Тест что AgentContextStore работает когда Langfuse disabled."""
        with patch("app.vectorstore.agent_context_store.get_langfuse") as mock_langfuse:
            mock_langfuse_instance = MagicMock()
            mock_langfuse_instance.enabled = False
            mock_langfuse.return_value = mock_langfuse_instance
            
            store = AgentContextStore(
                client=None,  # Qdrant disabled
                user_id=uuid4(),
                agent_name="test_agent",
            )
            
            # Should be disabled
            assert not store.enabled
            
            # But Langfuse instance should still be created
            assert store.langfuse is not None

    @pytest.mark.asyncio
    async def test_add_interaction_fallback_when_embedding_fails(self, context_store):
        """Тест fallback на hash-based embedding когда embedding API fails."""
        # Setup
        context_store._ensure_collection_exists = AsyncMock(return_value=True)
        context_store.client.upsert = AsyncMock()
        
        # Make embeddings fail
        context_store.openai_client.embeddings.create = AsyncMock(
            side_effect=Exception("Embedding API error")
        )
        
        # Call - должно работать с fallback
        point_id = await context_store.add_interaction(
            content="test content",
            interaction_type="user_message",
        )
        
        # Verify
        assert point_id != ""
        context_store.client.upsert.assert_called_once()
        
        # Verify that fallback embedding was used
        upsert_call = context_store.client.upsert.call_args
        points = upsert_call[1]["points"]
        assert len(points) == 1
        assert len(points[0].vector) == 1536  # Hash-based vector

    @pytest.mark.asyncio
    async def test_search_fallback_when_embedding_fails(self, context_store):
        """Тест fallback когда embedding search fails."""
        # Setup
        context_store._ensure_collection_exists = AsyncMock(return_value=True)
        
        # Make embeddings fail
        context_store.openai_client.embeddings.create = AsyncMock(
            side_effect=Exception("Embedding API error")
        )
        
        # Mock query_points
        mock_result = MagicMock()
        mock_result.points = []
        context_store.client.query_points = AsyncMock(return_value=mock_result)
        
        # Call - должно работать с fallback
        results = await context_store.search(query="test query")
        
        # Verify
        assert results == []
        context_store.client.query_points.assert_called_once()
        
        # Verify that fallback embedding was used
        query_call = context_store.client.query_points.call_args
        query_vector = query_call[1]["query"]
        assert len(query_vector) == 1536  # Hash-based vector
