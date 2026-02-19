"""Manager for user worker spaces with per-project architecture."""

import asyncio
from typing import Any, Optional
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent_bus import AgentBus
from app.core.user_worker_space import UserWorkerSpace
from app.logging_config import get_logger

logger = get_logger(__name__)


class WorkerSpaceManager:
    """Singleton manager for all user worker spaces.

    Each (user_id, project_id) pair has exactly one UserWorkerSpace.
    """

    _instance: Optional["WorkerSpaceManager"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "WorkerSpaceManager":
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize workspace manager."""
        if self._initialized:
            return

        self.spaces: dict[str, UserWorkerSpace] = {}
        self.agent_bus = AgentBus()
        self._initialized = True

        logger.info("worker_space_manager_initialized")

    def _make_key(self, user_id: UUID, project_id: str) -> str:
        """Create space key from user_id and project_id.

        Args:
            user_id: User ID
            project_id: Project ID

        Returns:
            Key string: f"{user_id}_{project_id}"
        """
        return f"{user_id}_{project_id}"

    async def get_or_create(
        self,
        user_id: UUID,
        project_id: str,
        db: AsyncSession,
        redis: Optional[Redis],
        qdrant: Optional[AsyncQdrantClient],
    ) -> UserWorkerSpace:
        """Get existing or create new worker space.

        Args:
            user_id: User ID
            project_id: Project ID
            db: Database session
            redis: Redis client
            qdrant: Qdrant client

        Returns:
            UserWorkerSpace instance
        """
        key = self._make_key(user_id, project_id)

        # Try fast path first
        if key in self.spaces:
            return self.spaces[key]

        # Slow path with lock
        async with self._lock:
            # Double-check after acquiring lock
            if key in self.spaces:
                return self.spaces[key]

            try:
                space = UserWorkerSpace(
                    user_id=user_id,
                    project_id=project_id,
                    db=db,
                    redis=redis,
                    qdrant=qdrant,
                    agent_bus=self.agent_bus,
                )

                # Initialize the space
                await space.initialize()

                # Store in manager
                self.spaces[key] = space

                logger.info(
                    "worker_space_created",
                    user_id=str(user_id),
                    project_id=project_id,
                    total_spaces=len(self.spaces),
                )

                return space
            except Exception as e:
                logger.error(
                    "worker_space_creation_error",
                    user_id=str(user_id),
                    project_id=project_id,
                    error=str(e),
                )
                raise

    async def get(
        self, user_id: UUID, project_id: str
    ) -> Optional[UserWorkerSpace]:
        """Get existing worker space.

        Args:
            user_id: User ID
            project_id: Project ID

        Returns:
            UserWorkerSpace or None if not exists
        """
        key = self._make_key(user_id, project_id)
        return self.spaces.get(key)

    async def remove(self, user_id: UUID, project_id: str) -> bool:
        """Remove worker space.

        Performs cleanup before removal.

        Args:
            user_id: User ID
            project_id: Project ID

        Returns:
            True if removed, False if not found
        """
        key = self._make_key(user_id, project_id)

        async with self._lock:
            if key not in self.spaces:
                logger.warning(
                    "worker_space_not_found",
                    user_id=str(user_id),
                    project_id=project_id,
                )
                return False

            try:
                space = self.spaces[key]
                await space.cleanup()
                del self.spaces[key]

                logger.info(
                    "worker_space_removed",
                    user_id=str(user_id),
                    project_id=project_id,
                    remaining_spaces=len(self.spaces),
                )

                return True
            except Exception as e:
                logger.error(
                    "worker_space_removal_error",
                    user_id=str(user_id),
                    project_id=project_id,
                    error=str(e),
                )
                return False

    async def remove_user_spaces(self, user_id: UUID) -> int:
        """Remove all spaces for a user.

        Called when user is deleted.

        Args:
            user_id: User ID

        Returns:
            Number of spaces removed
        """
        prefix = f"{user_id}_"
        keys_to_remove = [k for k in self.spaces.keys() if k.startswith(prefix)]

        removed_count = 0
        for key in keys_to_remove:
            try:
                space = self.spaces[key]
                await space.cleanup()
                del self.spaces[key]
                removed_count += 1
            except Exception as e:
                logger.error("space_cleanup_error", key=key, error=str(e))

        logger.info(
            "user_spaces_removed",
            user_id=str(user_id),
            removed_count=removed_count,
        )

        return removed_count

    async def get_user_spaces(self, user_id: UUID) -> list[UserWorkerSpace]:
        """Get all spaces for a user.

        Args:
            user_id: User ID

        Returns:
            List of worker spaces
        """
        prefix = f"{user_id}_"
        return [
            space for key, space in self.spaces.items() if key.startswith(prefix)
        ]

    async def cleanup_all(self) -> None:
        """Cleanup all worker spaces.

        Called during shutdown.
        """
        async with self._lock:
            for space in self.spaces.values():
                try:
                    await space.cleanup()
                except Exception as e:
                    logger.error("space_cleanup_error", error=str(e))

            self.spaces.clear()
            await self.agent_bus.cleanup()

            logger.info("all_worker_spaces_cleanup")

    def get_stats(self) -> dict[str, Any]:
        """Get manager statistics.

        Returns:
            Statistics dictionary with:
            - active_spaces: number of active spaces
            - spaces: per-space statistics (basic info only)
        
        Note:
            For detailed async stats, use individual workspace.get_metrics()
        """
        spaces_stats = {}
        for key, space in self.spaces.items():
            user_id_str, project_id = key.rsplit("_", 1)
            spaces_stats[key] = {
                "user_id": user_id_str,
                "project_id": project_id,
                "initialized": space.initialized,
                "active_agents": len(space.active_agents),
                "cache_size": space.agent_cache.get_size(),
            }

        return {
            "active_spaces": len(self.spaces),
            "spaces": spaces_stats,
        }

    def get_user_project_count(self, user_id: UUID) -> int:
        """Get number of active projects for user.

        Args:
            user_id: User ID

        Returns:
            Number of projects
        """
        prefix = f"{user_id}_"
        return sum(1 for k in self.spaces.keys() if k.startswith(prefix))


# Global manager instance
_manager_instance: Optional[WorkerSpaceManager] = None


def get_worker_space_manager() -> WorkerSpaceManager:
    """Get global worker space manager instance.

    Returns:
        WorkerSpaceManager singleton
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = WorkerSpaceManager()
    return _manager_instance
