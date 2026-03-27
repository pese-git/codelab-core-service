"""Database configuration and session management."""

import asyncio
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

try:
    import asyncpg
except ImportError:
    asyncpg = None

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


# Create async engine
engine: AsyncEngine = create_async_engine(
    str(settings.database_url),
    echo=settings.database_echo,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
    pool_pre_ping=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Get database session context manager."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database (create database and tables)."""
    db_url = str(settings.database_url)
    
    # For PostgreSQL, ensure database exists
    if "postgresql" in db_url and asyncpg:
        # Extract database name from URL
        # Format: postgresql+asyncpg://user:password@host:port/dbname
        match = re.search(r'/([^/?]+)(?:\?|$)', db_url)
        db_name = match.group(1) if match else None
        
        if db_name:
            # Parse connection parameters
            parsed = urlparse(db_url.replace("postgresql+asyncpg://", "postgresql://"))
            
            try:
                # Connect directly to postgres database using asyncpg
                conn = await asyncpg.connect(
                    host=parsed.hostname or 'localhost',
                    port=parsed.port or 5432,
                    user=parsed.username or 'postgres',
                    password=parsed.password or 'postgres',
                    database='postgres'
                )
                
                try:
                    # Check if database exists and create if not
                    exists = await conn.fetchval(
                        f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"
                    )
                    if not exists:
                        # CREATE DATABASE must be run outside a transaction
                        await conn.execute(f'CREATE DATABASE "{db_name}"')
                finally:
                    await conn.close()
            except Exception as e:
                # If asyncpg is not available or connection fails, continue
                # SQLAlchemy will fail with a better error message anyway
                pass
            
            # Small delay to ensure database is ready
            await asyncio.sleep(0.5)
    
    # Create tables in the target database
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
