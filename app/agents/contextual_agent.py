"""Contextual agent with RAG integration."""

from typing import Any
from uuid import UUID

import openai
from qdrant_client import AsyncQdrantClient

from app.config import settings
from app.logging_config import get_logger
from app.schemas.agent import AgentConfig
from app.vectorstore.agent_context_store import AgentContextStore

logger = get_logger(__name__)


class ContextualAgent:
    """Agent with context retrieval capabilities."""

    def __init__(
        self,
        agent_id: UUID,
        user_id: UUID,
        agent_name: str,
        config: AgentConfig,
        qdrant_client: AsyncQdrantClient | None,
    ):
        """Initialize contextual agent.
        
        Args:
            agent_id: Agent ID
            user_id: User ID
            agent_name: Agent name
            config: Agent configuration
            qdrant_client: Qdrant client instance, or None if Qdrant is disabled
        """
        self.agent_id = agent_id
        self.user_id = user_id
        self.agent_name = agent_name
        self.config = config
        
        # Initialize OpenAI client (supports LiteLLM via base_url)
        client_kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        self.openai_client = openai.AsyncOpenAI(**client_kwargs)
        
        # Initialize context store
        self.context_store = AgentContextStore(
            client=qdrant_client,
            user_id=user_id,
            agent_name=agent_name,
        )

    async def initialize(self) -> None:
        """Initialize agent (create Qdrant collection)."""
        await self.context_store.initialize()
        logger.info(
            "agent_initialized",
            agent_id=str(self.agent_id),
            agent_name=self.agent_name,
        )

    async def execute(
        self,
        user_message: str,
        session_history: list[dict[str, str]] | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute agent with context retrieval."""
        try:
            # Retrieve relevant context
            context_results = await self.context_store.search(
                query=user_message,
                limit=settings.context_search_limit,
                filter_success=True,
            )

            # Build context string
            context_str = ""
            if context_results:
                context_str = "\n\n## Relevant Context:\n"
                for i, result in enumerate(context_results, 1):
                    context_str += f"\n{i}. {result['content']}\n"

            # Build messages
            messages = [
                {"role": "system", "content": self.config.system_prompt + context_str}
            ]

            # Add session history
            if session_history:
                messages.extend(session_history[-10:])  # Last 10 messages

            # Add user message
            messages.append({"role": "user", "content": user_message})

            # Call LLM
            response = await self.openai_client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            assistant_message = response.choices[0].message.content or ""

            # Store interaction in context
            await self.context_store.add_interaction(
                content=f"User: {user_message}\nAssistant: {assistant_message}",
                interaction_type="chat",
                task_id=task_id,
                success=True,
                metadata={
                    "model": self.config.model,
                    "tokens": response.usage.total_tokens if response.usage else 0,
                },
            )

            logger.info(
                "agent_executed",
                agent_id=str(self.agent_id),
                agent_name=self.agent_name,
                task_id=task_id,
                context_used=len(context_results),
            )

            return {
                "success": True,
                "response": assistant_message,
                "context_used": len(context_results),
                "tokens_used": response.usage.total_tokens if response.usage else 0,
            }

        except openai.APITimeoutError as e:
            error_msg = f"LLM request timeout: model '{self.config.model}' did not respond in time"
            logger.error(
                "agent_execution_failed",
                agent_id=str(self.agent_id),
                agent_name=self.agent_name,
                error=error_msg,
                error_type="timeout",
                model=self.config.model,
                provider=settings.openai_base_url or "openai",
            )

            # Store failed interaction
            await self.context_store.add_interaction(
                content=f"User: {user_message}\nError: {error_msg}",
                interaction_type="chat",
                task_id=task_id,
                success=False,
            )

            return {
                "success": False,
                "error": error_msg,
                "error_type": "timeout",
                "provider": settings.openai_base_url or "openai",
                "model": self.config.model,
            }

        except openai.APIConnectionError as e:
            error_msg = f"Failed to connect to LLM provider: {str(e)}"
            logger.error(
                "agent_execution_failed",
                agent_id=str(self.agent_id),
                agent_name=self.agent_name,
                error=error_msg,
                error_type="connection",
                model=self.config.model,
                provider=settings.openai_base_url or "openai",
            )

            # Store failed interaction
            await self.context_store.add_interaction(
                content=f"User: {user_message}\nError: {error_msg}",
                interaction_type="chat",
                task_id=task_id,
                success=False,
            )

            return {
                "success": False,
                "error": error_msg,
                "error_type": "connection",
                "provider": settings.openai_base_url or "openai",
                "model": self.config.model,
            }

        except openai.RateLimitError as e:
            error_msg = f"LLM provider rate limit exceeded for model '{self.config.model}'"
            logger.error(
                "agent_execution_failed",
                agent_id=str(self.agent_id),
                agent_name=self.agent_name,
                error=error_msg,
                error_type="rate_limit",
                model=self.config.model,
                provider=settings.openai_base_url or "openai",
            )

            # Store failed interaction
            await self.context_store.add_interaction(
                content=f"User: {user_message}\nError: {error_msg}",
                interaction_type="chat",
                task_id=task_id,
                success=False,
            )

            return {
                "success": False,
                "error": error_msg,
                "error_type": "rate_limit",
                "provider": settings.openai_base_url or "openai",
                "model": self.config.model,
            }

        except openai.AuthenticationError as e:
            error_msg = f"LLM provider authentication failed: invalid API key"
            logger.error(
                "agent_execution_failed",
                agent_id=str(self.agent_id),
                agent_name=self.agent_name,
                error=error_msg,
                error_type="authentication",
                model=self.config.model,
                provider=settings.openai_base_url or "openai",
            )

            # Store failed interaction
            await self.context_store.add_interaction(
                content=f"User: {user_message}\nError: {error_msg}",
                interaction_type="chat",
                task_id=task_id,
                success=False,
            )

            return {
                "success": False,
                "error": error_msg,
                "error_type": "authentication",
                "provider": settings.openai_base_url or "openai",
                "model": self.config.model,
            }

        except openai.BadRequestError as e:
            error_msg = f"Invalid request to LLM provider: {str(e)}"
            logger.error(
                "agent_execution_failed",
                agent_id=str(self.agent_id),
                agent_name=self.agent_name,
                error=error_msg,
                error_type="bad_request",
                model=self.config.model,
                provider=settings.openai_base_url or "openai",
            )

            # Store failed interaction
            await self.context_store.add_interaction(
                content=f"User: {user_message}\nError: {error_msg}",
                interaction_type="chat",
                task_id=task_id,
                success=False,
            )

            return {
                "success": False,
                "error": error_msg,
                "error_type": "bad_request",
                "provider": settings.openai_base_url or "openai",
                "model": self.config.model,
            }

        except Exception as e:
            error_msg = f"Unexpected error during LLM execution: {str(e)}"
            logger.error(
                "agent_execution_failed",
                agent_id=str(self.agent_id),
                agent_name=self.agent_name,
                error=error_msg,
                error_type="unknown",
                model=self.config.model,
            )

            # Store failed interaction
            await self.context_store.add_interaction(
                content=f"User: {user_message}\nError: {error_msg}",
                interaction_type="chat",
                task_id=task_id,
                success=False,
            )

            return {
                "success": False,
                "error": error_msg,
                "error_type": "unknown",
                "model": self.config.model,
            }

    async def get_context_stats(self) -> dict[str, Any]:
        """Get context statistics."""
        return await self.context_store.get_stats()

    async def clear_context(self) -> None:
        """Clear agent context."""
        await self.context_store.clear()
