"""Main FastAPI application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.config import settings
from app.database import close_db, init_db
from app.logging_config import configure_logging, get_logger
from app.middleware.user_isolation import UserIsolationMiddleware
from app.qdrant_client import close_qdrant
from app.redis_client import close_redis
from app.routes import health, streaming, projects, project_agents, project_chat
from app.core.stream_manager import close_stream_manager

# Configure logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("application_starting", version=settings.app_version)
    
    # Initialize database (create tables if needed)
    # Note: In production, use Alembic migrations instead
    if settings.debug:
        await init_db()
    
    logger.info("application_started")
    
    yield
    
    # Shutdown
    logger.info("application_shutting_down")
    await close_stream_manager()
    await close_db()
    await close_redis()
    await close_qdrant()
    logger.info("application_stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Personal Multi-Agent AI Platform - Core Service",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


def custom_openapi():
    """Custom OpenAPI schema with Bearer Authentication."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT токен. Токен должен содержать claim 'sub' с UUID пользователя."
        }
    }
    
    openapi_schema["security"] = [{"BearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Set custom OpenAPI schema
app.openapi = custom_openapi

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Add user isolation middleware
app.add_middleware(UserIsolationMiddleware)

# Include routers
app.include_router(health.router)
app.include_router(projects.router)
app.include_router(project_agents.router)
app.include_router(project_chat.router)
app.include_router(streaming.project_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
