"""Qdrant client configuration."""

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from app.config import settings

# Global Qdrant client instance
_qdrant_client: AsyncQdrantClient | None = None


async def get_qdrant() -> AsyncQdrantClient:
    """Get Qdrant client instance."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=settings.qdrant_timeout,
            prefer_grpc=settings.qdrant_prefer_grpc,
        )
    return _qdrant_client


async def close_qdrant() -> None:
    """Close Qdrant connection."""
    global _qdrant_client
    if _qdrant_client is not None:
        await _qdrant_client.close()
        _qdrant_client = None


async def ensure_collection(
    client: AsyncQdrantClient,
    collection_name: str,
    vector_size: int = 1536,  # OpenAI text-embedding-3-small
    distance: Distance = Distance.COSINE,
) -> None:
    """Ensure collection exists, create if not."""
    collections = await client.get_collections()
    collection_names = [c.name for c in collections.collections]
    
    if collection_name not in collection_names:
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=distance,
            ),
        )
