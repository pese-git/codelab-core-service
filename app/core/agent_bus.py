"""Agent bus for task coordination."""

import asyncio
from typing import Any, Callable
from uuid import UUID

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class TaskItem:
    """Task item for agent queue."""

    def __init__(
        self,
        task_id: str,
        agent_id: UUID,
        payload: dict[str, Any],
        callback: Callable[[dict[str, Any]], Any] | None = None,
    ):
        self.task_id = task_id
        self.agent_id = agent_id
        self.payload = payload
        self.callback = callback
        self.result: dict[str, Any] | None = None
        self.error: Exception | None = None
        self.completed = asyncio.Event()


class AgentBus:
    """Agent bus for coordinating agent tasks."""

    def __init__(self):
        """Initialize agent bus."""
        self.queues: dict[UUID, asyncio.Queue[TaskItem]] = {}
        self.workers: dict[UUID, asyncio.Task[None]] = {}
        self.agent_handlers: dict[UUID, Callable[[TaskItem], Any]] = {}
        self.max_concurrency: dict[UUID, int] = {}
        self.active_tasks: dict[UUID, int] = {}

    async def register_agent(
        self,
        agent_id: UUID,
        handler: Callable[[TaskItem], Any],
        max_concurrency: int = 3,
    ) -> None:
        """Register agent with the bus."""
        if agent_id in self.queues:
            logger.warning("agent_already_registered", agent_id=str(agent_id))
            return

        self.queues[agent_id] = asyncio.Queue(maxsize=settings.agent_queue_size)
        self.agent_handlers[agent_id] = handler
        self.max_concurrency[agent_id] = max_concurrency
        self.active_tasks[agent_id] = 0

        # Start worker
        self.workers[agent_id] = asyncio.create_task(self._worker(agent_id))

        logger.info(
            "agent_registered",
            agent_id=str(agent_id),
            max_concurrency=max_concurrency,
        )

    async def deregister_agent(self, agent_id: UUID) -> None:
        """Deregister agent from the bus."""
        if agent_id not in self.queues:
            logger.warning("agent_not_registered", agent_id=str(agent_id))
            return

        # Cancel worker
        if agent_id in self.workers:
            self.workers[agent_id].cancel()
            try:
                await self.workers[agent_id]
            except asyncio.CancelledError:
                pass
            del self.workers[agent_id]

        # Clean up
        del self.queues[agent_id]
        del self.agent_handlers[agent_id]
        del self.max_concurrency[agent_id]
        del self.active_tasks[agent_id]

        logger.info("agent_deregistered", agent_id=str(agent_id))

    async def submit_task(
        self,
        agent_id: UUID,
        task_id: str,
        payload: dict[str, Any],
        callback: Callable[[dict[str, Any]], Any] | None = None,
    ) -> TaskItem:
        """Submit task to agent queue."""
        if agent_id not in self.queues:
            raise ValueError(f"Agent {agent_id} not registered")

        task_item = TaskItem(task_id, agent_id, payload, callback)

        try:
            await asyncio.wait_for(
                self.queues[agent_id].put(task_item),
                timeout=5.0,
            )
            logger.info(
                "task_submitted",
                task_id=task_id,
                agent_id=str(agent_id),
                queue_size=self.queues[agent_id].qsize(),
            )
        except asyncio.TimeoutError:
            logger.error(
                "task_submission_timeout",
                task_id=task_id,
                agent_id=str(agent_id),
            )
            raise ValueError("Agent queue is full")

        return task_item

    async def _worker(self, agent_id: UUID) -> None:
        """Worker task for processing agent queue."""
        logger.info("worker_started", agent_id=str(agent_id))

        try:
            while True:
                # Wait for task
                task_item = await self.queues[agent_id].get()

                # Check concurrency limit
                while self.active_tasks[agent_id] >= self.max_concurrency[agent_id]:
                    await asyncio.sleep(0.1)

                # Process task
                self.active_tasks[agent_id] += 1
                asyncio.create_task(self._process_task(agent_id, task_item))

        except asyncio.CancelledError:
            logger.info("worker_cancelled", agent_id=str(agent_id))
            raise

    async def _process_task(self, agent_id: UUID, task_item: TaskItem) -> None:
        """Process individual task."""
        try:
            logger.info(
                "task_started",
                task_id=task_item.task_id,
                agent_id=str(agent_id),
            )

            # Execute handler
            handler = self.agent_handlers[agent_id]
            result = await handler(task_item)

            task_item.result = result
            logger.info(
                "task_completed",
                task_id=task_item.task_id,
                agent_id=str(agent_id),
            )

        except Exception as e:
            task_item.error = e
            logger.error(
                "task_failed",
                task_id=task_item.task_id,
                agent_id=str(agent_id),
                error=str(e),
            )

        finally:
            self.active_tasks[agent_id] -= 1
            task_item.completed.set()

            # Call callback if provided
            if task_item.callback:
                try:
                    await task_item.callback(task_item.result or {})
                except Exception as e:
                    logger.error(
                        "callback_failed",
                        task_id=task_item.task_id,
                        error=str(e),
                    )

    def get_queue_size(self, agent_id: UUID) -> int:
        """Get current queue size for agent."""
        if agent_id not in self.queues:
            return 0
        return self.queues[agent_id].qsize()

    def get_active_tasks(self, agent_id: UUID) -> int:
        """Get number of active tasks for agent."""
        return self.active_tasks.get(agent_id, 0)

    def get_stats(self) -> dict[str, Any]:
        """Get bus statistics."""
        return {
            "registered_agents": len(self.queues),
            "total_queue_size": sum(q.qsize() for q in self.queues.values()),
            "total_active_tasks": sum(self.active_tasks.values()),
            "agents": {
                str(agent_id): {
                    "queue_size": self.queues[agent_id].qsize(),
                    "active_tasks": self.active_tasks[agent_id],
                    "max_concurrency": self.max_concurrency[agent_id],
                }
                for agent_id in self.queues
            },
        }

    async def cleanup(self) -> None:
        """Cleanup all agents and workers.
        
        Called during shutdown to gracefully stop all workers
        and clear all queues and handlers.
        """
        logger.info("agent_bus_cleanup_started", agent_count=len(self.queues))

        # Cancel all workers
        for agent_id in list(self.workers.keys()):
            try:
                await self.deregister_agent(agent_id)
            except Exception as e:
                logger.error(
                    "agent_deregister_error",
                    agent_id=str(agent_id),
                    error=str(e),
                )

        # Clear all remaining data structures
        self.queues.clear()
        self.agent_handlers.clear()
        self.max_concurrency.clear()
        self.active_tasks.clear()

        logger.info("agent_bus_cleanup_completed")
