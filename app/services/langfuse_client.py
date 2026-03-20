"""Langfuse client initialization and management."""

from typing import Optional
from uuid import UUID

from langfuse import Langfuse, get_client

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class LangfuseClient:
    """Manages Langfuse SDK initialization and tracing context."""

    def __init__(self) -> None:
        """Initialize Langfuse client based on settings."""
        self.client: Optional[Langfuse] = None
        self.enabled = settings.langfuse_enabled and settings.langfuse_tracing_enabled

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
            base_url = settings.langfuse_base_url or settings.langfuse_host
            self.client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=base_url,
                tracing_enabled=self.enabled,
                debug=settings.langfuse_debug,
            )

            logger.info(
                "langfuse_client_initialized",
                base_url=base_url,
                debug=settings.langfuse_debug,
            )

        except Exception as e:
            logger.error(
                "langfuse_initialization_failed",
                error=str(e),
            )
            self.enabled = False

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


def _update_langfuse_span(*, input_data: dict | None = None, output_data: dict | None = None) -> None:
    """Safely attach sanitized IO payload to current Langfuse span."""
    try:
        get_client().update_current_span(input=input_data, output=output_data)
    except Exception:
        logger.debug("langfuse_span_update_skipped", exc_info=True)


def _sanitize_langfuse_attr(value: object) -> str:
    """Langfuse attributes must be ASCII strings <= 200 chars."""
    if value is None:
        return ""
    text = str(value)
    text = text.encode("ascii", "ignore").decode("ascii")
    return text[:200]
