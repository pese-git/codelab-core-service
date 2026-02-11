"""Main FastAPI application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import close_db, init_db
from app.logging_config import configure_logging, get_logger
from app.middleware.user_isolation import UserIsolationMiddleware
from app.qdrant_client import close_qdrant
from app.redis_client import close_redis
from app.routes import agents, chat, health

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
    await close_db()
    await close_redis()
    await close_qdrant()
    logger.info("application_stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Personal Multi-Agent AI Platform - Core Service",
    docs_url="/my/docs",
    openapi_url="/my/openapi.json",
    lifespan=lifespan,
)

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
app.include_router(agents.router)
app.include_router(chat.router)


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
