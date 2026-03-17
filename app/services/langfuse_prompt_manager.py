"""Langfuse Prompt Management integration."""

from __future__ import annotations

from typing import Any, Optional

from app.config import settings
from app.logging_config import get_logger
from app.services.langfuse_client import LangfuseClient, get_langfuse_client

logger = get_logger(__name__)


class LangfusePromptManager:
    """Fetches and compiles prompts from Langfuse Prompt Management."""

    def __init__(self, langfuse_client: LangfuseClient) -> None:
        self._langfuse = langfuse_client

    def _enabled(self) -> bool:
        return (
            settings.langfuse_prompt_management_enabled
            and self._langfuse.enabled
            and self._langfuse.client is not None
        )

    @staticmethod
    def _compile_fallback(template: str, variables: dict[str, Any] | None) -> str:
        if not variables:
            return template
        compiled = template
        for key, value in variables.items():
            compiled = compiled.replace(f"{{{{{key}}}}}", str(value))
        return compiled

    def get_text_prompt(
        self,
        *,
        name: str,
        variables: dict[str, Any] | None = None,
        label: str | None = None,
        version: int | None = None,
        fallback: str,
    ) -> tuple[str, Optional[Any]]:
        """Return compiled text prompt and the prompt object for trace linking."""
        if label and version:
            logger.warning(
                "langfuse_prompt_label_and_version_provided",
                name=name,
            )
            version = None

        if not self._enabled():
            return self._compile_fallback(fallback, variables), None

        try:
            prompt = self._langfuse.client.get_prompt(
                name=name,
                type="text",
                label=label,
                version=version,
                cache_ttl_seconds=settings.langfuse_prompt_cache_ttl_seconds,
                fetch_timeout_seconds=settings.langfuse_prompt_fetch_timeout_seconds,
                max_retries=settings.langfuse_prompt_max_retries,
                fallback=fallback,
            )
            if hasattr(prompt, "compile"):
                compiled = prompt.compile(**(variables or {}))
            else:
                compiled = self._compile_fallback(fallback, variables)
            logger.info(
                "langfuse_prompt_resolved",
                name=name,
                label=label,
                version=version,
            )
            return compiled, prompt
        except Exception as exc:
            logger.warning(
                "langfuse_prompt_fetch_failed",
                name=name,
                error=str(exc),
            )
            return self._compile_fallback(fallback, variables), None


_prompt_manager: Optional[LangfusePromptManager] = None


def get_langfuse_prompt_manager() -> LangfusePromptManager:
    """Get or create a singleton LangfusePromptManager."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = LangfusePromptManager(get_langfuse_client())
    return _prompt_manager
