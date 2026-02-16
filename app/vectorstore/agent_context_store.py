"""Agent context store using Qdrant."""

from datetime import datetime
from typing import Any
from uuid import UUID

import openai
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import settings
from app.logging_config import get_logger
from app.qdrant_client import ensure_collection

logger = get_logger(__name__)


class AgentContextStore:
    """Store and retrieve agent context using Qdrant vector database."""

    def __init__(self, client: AsyncQdrantClient | None, user_id: UUID, agent_name: str):
        """Initialize agent context store.
        
        Args:
            client: Qdrant client instance, or None if Qdrant is disabled
            user_id: User ID
            agent_name: Agent name
        """
        self.client = client
        self.user_id = user_id
        self.agent_name = agent_name
        self.collection_name = f"user{user_id}_{agent_name}_context"
        self.enabled = client is not None
        
        # Initialize OpenAI client (supports LiteLLM via base_url)
        client_kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        self.openai_client = openai.AsyncOpenAI(**client_kwargs)

    async def _ensure_collection_exists(self) -> bool:
        """Check if collection exists and initialize if needed.
        
        Returns False if Qdrant is disabled.
        """
        if not self.enabled:
            return False
        
        try:
            await self.client.get_collection(collection_name=self.collection_name)
            return True
        except Exception:
            # Collection doesn't exist, initialize it
            await self.initialize()
            return False

    async def initialize(self) -> None:
        """Initialize collection if not exists.
        
        Does nothing if Qdrant is disabled.
        """
        if not self.enabled:
            logger.info(
                "agent_context_disabled",
                user_id=str(self.user_id),
                agent_name=self.agent_name,
            )
            return
        
        await ensure_collection(
            self.client,
            self.collection_name,
            vector_size=1536,  # OpenAI text-embedding-3-small
            distance=Distance.COSINE,
        )
        logger.info(
            "agent_context_initialized",
            collection=self.collection_name,
            user_id=str(self.user_id),
            agent_name=self.agent_name,
        )

    async def add_interaction(
        self,
        content: str,
        interaction_type: str,
        task_id: str | None = None,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add interaction to agent context.
        
        Returns empty string if Qdrant is disabled.
        """
        if not self.enabled:
            return ""
        
        # Generate embedding
        try:
            response = await self.openai_client.embeddings.create(
                model=settings.openai_embedding_model,
                input=content,
            )
            embedding = response.data[0].embedding
        except Exception as e:
            # Fallback: if embeddings fail, use a simple hash-based vector
            # This allows the system to work even without proper embeddings
            logger.warning(
                "embedding_failed_using_fallback",
                error=str(e),
                collection=self.collection_name,
            )
            # Create a simple 1536-dim vector from content hash
            import hashlib
            hash_obj = hashlib.sha256(content.encode())
            hash_bytes = hash_obj.digest()
            # Repeat and normalize to create 1536-dim vector
            embedding = []
            for i in range(1536):
                embedding.append((hash_bytes[i % len(hash_bytes)] / 255.0) - 0.5)

        # Create point
        point_id = str(UUID(int=hash(content) & 0xFFFFFFFFFFFFFFFF))
        payload = {
            "content": content,
            "interaction_type": interaction_type,
            "task_id": task_id,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }

        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload=payload,
        )

        # Ensure collection exists before upserting
        await self._ensure_collection_exists()
        
        # Upsert to collection
        await self.client.upsert(
            collection_name=self.collection_name,
            points=[point],
        )

        logger.info(
            "interaction_added",
            collection=self.collection_name,
            point_id=point_id,
            interaction_type=interaction_type,
        )

        return point_id

    async def search(
        self,
        query: str,
        limit: int = 10,
        filter_success: bool | None = None,
        filter_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for relevant context.
        
        Returns empty list if Qdrant is disabled.
        """
        if not self.enabled:
            return []
        
        # Ensure collection exists
        collection_existed = await self._ensure_collection_exists()
        if not collection_existed:
            return []  # Return empty results for newly created collection
        
        # Generate query embedding
        try:
            response = await self.openai_client.embeddings.create(
                model=settings.openai_embedding_model,
                input=query,
            )
            query_embedding = response.data[0].embedding
        except Exception as e:
            # Fallback: if embeddings fail, use a simple hash-based vector
            logger.warning(
                "embedding_search_failed_using_fallback",
                error=str(e),
                collection=self.collection_name,
            )
            import hashlib
            hash_obj = hashlib.sha256(query.encode())
            hash_bytes = hash_obj.digest()
            query_embedding = []
            for i in range(1536):
                query_embedding.append((hash_bytes[i % len(hash_bytes)] / 255.0) - 0.5)

        # Build filter
        search_filter = None
        if filter_success is not None or filter_type is not None:
            conditions = []
            if filter_success is not None:
                conditions.append({"key": "success", "match": {"value": filter_success}})
            if filter_type is not None:
                conditions.append({"key": "interaction_type", "match": {"value": filter_type}})
            
            if conditions:
                search_filter = {"must": conditions}

        # Search (use query method for async client)
        results = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=limit,
            query_filter=search_filter,
        )
        results = results.points if hasattr(results, 'points') else results

        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.id,
                "score": result.score,
                "content": result.payload.get("content"),
                "interaction_type": result.payload.get("interaction_type"),
                "task_id": result.payload.get("task_id"),
                "success": result.payload.get("success"),
                "timestamp": result.payload.get("timestamp"),
                "metadata": result.payload.get("metadata", {}),
            })

        logger.info(
            "context_searched",
            collection=self.collection_name,
            query_length=len(query),
            results_count=len(formatted_results),
        )

        return formatted_results

    async def clear(self) -> None:
        """Clear all context for this agent.
        
        Does nothing if Qdrant is disabled.
        """
        if not self.enabled:
            return
        
        try:
            await self.client.delete_collection(collection_name=self.collection_name)
        except Exception as e:
            logger.warning(
                "collection_delete_failed",
                collection=self.collection_name,
                error=str(e),
            )
        await self.initialize()
        logger.info("context_cleared", collection=self.collection_name)

    async def get_stats(self) -> dict[str, Any]:
        """Get context statistics.
        
        Returns minimal stats if Qdrant is disabled.
        """
        if not self.enabled:
            return {
                "collection_name": self.collection_name,
                "total_vectors": 0,
                "vector_size": 0,
                "distance": "disabled",
                "enabled": False,
            }
        
        # Ensure collection exists
        await self._ensure_collection_exists()
        collection_info = await self.client.get_collection(collection_name=self.collection_name)
        
        return {
            "collection_name": self.collection_name,
            "total_vectors": collection_info.points_count,
            "vector_size": collection_info.config.params.vectors.size,
            "distance": collection_info.config.params.vectors.distance.name,
            "enabled": True,
        }

    async def prune(self, max_vectors: int | None = None) -> int:
        """Prune old vectors if exceeding limit.
        
        Returns 0 if Qdrant is disabled.
        """
        if not self.enabled:
            return 0
        
        if max_vectors is None:
            max_vectors = settings.context_max_vectors_per_agent

        stats = await self.get_stats()
        total_vectors = stats["total_vectors"]

        if total_vectors <= max_vectors:
            return 0

        # Calculate how many to delete
        to_delete = int(total_vectors - max_vectors * settings.context_prune_threshold)

        # Get oldest points (by timestamp)
        # Note: This is a simplified implementation
        # In production, you'd want to scroll through points and delete oldest
        logger.warning(
            "context_pruning_needed",
            collection=self.collection_name,
            total_vectors=total_vectors,
            max_vectors=max_vectors,
            to_delete=to_delete,
        )

        return to_delete
