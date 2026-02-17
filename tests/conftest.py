"""Test configuration and fixtures."""

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.user_project import UserProject
from app.models.user_agent import UserAgent
from app.models.chat_session import ChatSession
from app.redis_client import get_redis
from app.qdrant_client import get_qdrant


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create test user."""
    user = User(
        id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        email="test@example.com",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_project(db_session: AsyncSession, test_user: User) -> UserProject:
    """Create test project."""
    project = UserProject(
        user_id=test_user.id,
        name="test_project",
        workspace_path="/tmp/test_workspace",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def test_agent(db_session: AsyncSession, test_user: User, test_project: UserProject) -> UserAgent:
    """Create test agent."""
    agent = UserAgent(
        user_id=test_user.id,
        project_id=test_project.id,
        name="test_agent",
        config={
            "system_prompt": "You are a helpful assistant",
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 2048
        }
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest_asyncio.fixture
async def test_agents_fixture(db_session: AsyncSession, test_user: User, test_project: UserProject) -> list[UserAgent]:
    """Create test agents for worker space tests."""
    agents = []
    configs = [
        {
            "name": "test_coder",
            "system_prompt": "You are a coder",
            "model": "gpt-4",
            "temperature": 0.3,
            "max_tokens": 4096,
        },
        {
            "name": "test_analyzer",
            "system_prompt": "You are an analyzer",
            "model": "gpt-4",
            "temperature": 0.5,
            "max_tokens": 2048,
        },
    ]

    for config in configs:
        agent = UserAgent(
            user_id=test_user.id,
            project_id=test_project.id,
            name=config["name"],
            config=config,
            status="ready",
        )
        db_session.add(agent)
        agents.append(agent)

    await db_session.commit()
    for agent in agents:
        await db_session.refresh(agent)

    return agents


@pytest.fixture
def test_jwt_token(test_user: User) -> str:
    """Generate test JWT token."""
    from jose import jwt
    from datetime import datetime, timedelta, timezone
    
    payload = {
        "sub": str(test_user.id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    return token


@pytest.fixture
def auth_headers(test_jwt_token: str) -> dict:
    """Create authorization headers."""
    return {
        "Authorization": f"Bearer {test_jwt_token}",
        "Content-Type": "application/json",
    }


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database override."""
    from httpx import ASGITransport
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
def sync_client() -> TestClient:
    """Create synchronous test client."""
    return TestClient(app)


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.delete = AsyncMock(return_value=1)
    return redis_mock


@pytest.fixture
def mock_qdrant() -> AsyncMock:
    """Create mock Qdrant client."""
    qdrant_mock = AsyncMock()
    qdrant_mock.create_collection = AsyncMock(return_value=True)
    qdrant_mock.delete_collection = AsyncMock(return_value=True)
    qdrant_mock.collection_exists = AsyncMock(return_value=False)
    return qdrant_mock


@pytest_asyncio.fixture
async def client_with_mocks(
    db_session: AsyncSession,
    mock_redis: AsyncMock,
    mock_qdrant: AsyncMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database and service mocks."""
    from httpx import ASGITransport
    
    async def override_get_db():
        yield db_session
    
    async def override_get_redis():
        return mock_redis
    
    async def override_get_qdrant():
        return mock_qdrant
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_qdrant] = override_get_qdrant
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
    
    app.dependency_overrides.clear()
