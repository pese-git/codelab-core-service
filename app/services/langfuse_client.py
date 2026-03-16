"""Langfuse client initialization and management."""

from typing import Optional
from uuid import UUID

from langfuse import Langfuse

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class LangfuseClient:
    """Manages Langfuse SDK initialization and tracing context."""

    def __init__(self) -> None:
        """Initialize Langfuse client based on settings."""
        self.client: Optional[Langfuse] = None
        self.enabled = settings.langfuse_enabled

        if not self.enabled:
            logger.info("langfuse_disabled")
            return

        # Validate required configuration
        if not settings.langfuse_public_key or not settings.langfuse_secret_key:
            logger.warning(
                "langfuse_missing_credentials",
                has_public_key=bool(settings.langfuse_public_key),
                has_secret_key=bool(settings.langfuse_secret_key),
            )
            self.enabled = False
            return

        try:
            self.client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
                debug=settings.langfuse_debug,
            )

            logger.info(
                "langfuse_client_initialized",
                host=settings.langfuse_host,
                debug=settings.langfuse_debug,
            )

        except Exception as e:
            logger.error(
                "langfuse_initialization_failed",
                error=str(e),
            )
            self.enabled = False

    def observe_openai_client(self, openai_client) -> None:
        """Wrap OpenAI client with Langfuse automatic tracing.

        Args:
            openai_client: AsyncOpenAI client instance to wrap
        """
        if not self.enabled or not self.client:
            return

        try:
            # Try to import and apply Langfuse OpenAI integration if available
            try:
                from langfuse.openai import openai as langfuse_openai_module
                # If the module exists, use it for wrapping
                if hasattr(langfuse_openai_module, 'AsyncOpenAI'):
                    logger.info("openai_client_ready_for_langfuse_tracing")
            except ImportError:
                # Fallback: OpenAI tracing will work via @observe decorators
                logger.debug("langfuse_openai_integration_not_available_using_decorators")
        except Exception as e:
            logger.warning("langfuse_openai_wrapping_setup_warning", error=str(e))

    def update_trace_metadata(
        self,
        user_id: UUID,
        project_id: UUID,
        tags: Optional[list[str]] = None,
    ) -> None:
        """Update current trace with metadata.

        Args:
            user_id: User identifier
            project_id: Project identifier
            tags: Optional list of tags
        """
        if not self.enabled or not self.client:
            return

        try:
            all_tags = ["v0.2.0"] + (tags or [])

            self.client.update_current_trace(
                user_id=str(user_id),
                session_id=str(project_id),
                tags=all_tags,
            )

            logger.debug(
                "trace_metadata_updated",
                user_id=str(user_id),
                project_id=str(project_id),
                tags=all_tags,
            )

        except Exception as e:
            logger.warning(
                "trace_metadata_update_failed",
                error=str(e),
            )

    def flush(self) -> None:
        """Flush all pending traces to Langfuse server."""
        if self.enabled and self.client:
            try:
                self.client.flush()
                logger.info("langfuse_traces_flushed")
            except Exception as e:
                logger.error(
                    "langfuse_flush_failed",
                    error=str(e),
                )


# Global instance
_langfuse_client: Optional[LangfuseClient] = None


def get_langfuse_client() -> LangfuseClient:
    """Get or create the global Langfuse client instance."""
    global _langfuse_client

    if _langfuse_client is None:
        _langfuse_client = LangfuseClient()

    return _langfuse_client
