"""Application configuration."""

from functools import lru_cache
from typing import Any

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="codelab-core-service")
    app_version: str = Field(default="0.1.0")
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    workers: int = Field(default=4)
    reload: bool = Field(default=False)

    # Database (PostgreSQL)
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/codelab"
    )
    database_pool_size: int = Field(default=10)
    database_max_overflow: int = Field(default=20)
    database_pool_timeout: int = Field(default=30)
    database_echo: bool = Field(default=False)

    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    redis_max_connections: int = Field(default=50)
    redis_socket_timeout: int = Field(default=5)
    redis_socket_connect_timeout: int = Field(default=5)

    # Qdrant
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: str | None = Field(default=None)
    qdrant_timeout: int = Field(default=30)
    qdrant_prefer_grpc: bool = Field(default=False)

    # JWT Authentication
    jwt_secret_key: str = Field(default="your-secret-key-change-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=30)
    jwt_refresh_token_expire_days: int = Field(default=7)

    # OpenAI / LiteLLM
    openai_api_key: str = Field(default="")
    openai_base_url: str | None = Field(default=None)  # For LiteLLM or custom endpoints
    openai_model: str = Field(default="openrouter/openai/gpt-4.1")
    openai_embedding_model: str = Field(default="text-embedding-3-small")
    openai_max_retries: int = Field(default=3)
    openai_timeout: int = Field(default=60)

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=100)
    rate_limit_burst: int = Field(default=20)

    # SSE
    sse_heartbeat_interval: int = Field(default=30)
    sse_max_connections_per_user: int = Field(default=1000)
    sse_event_buffer_size: int = Field(default=100)
    sse_event_ttl: int = Field(default=300)

    # Agent Bus
    agent_max_concurrency: int = Field(default=3)
    agent_queue_size: int = Field(default=100)
    agent_task_timeout: int = Field(default=600)

    # Approval Manager
    approval_timeout: int = Field(default=300)
    approval_warning_before_timeout: int = Field(default=60)
    approval_max_retries: int = Field(default=3)

    # Context Store
    context_max_vectors_per_agent: int = Field(default=1000000)
    context_search_limit: int = Field(default=10)
    context_prune_threshold: float = Field(default=0.9)

    # Monitoring
    prometheus_enabled: bool = Field(default=True)
    prometheus_port: int = Field(default=9090)

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"]
    )
    cors_allow_credentials: bool = Field(default=True)
    cors_allow_methods: list[str] = Field(default=["*"])
    cors_allow_headers: list[str] = Field(default=["*"])

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v: Any) -> Any:
        """Validate database URL."""
        if isinstance(v, str):
            return v
        return v

    @field_validator("redis_url", mode="before")
    @classmethod
    def validate_redis_url(cls, v: Any) -> Any:
        """Validate Redis URL."""
        if isinstance(v, str):
            return v
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
