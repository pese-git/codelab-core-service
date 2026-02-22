#!/usr/bin/env python3
"""Initialize database with seed data."""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.models import User, UserProject, UserAgent
from app.core.starter_pack import initialize_starter_pack


async def create_seed_data() -> None:
    """Create seed data for development."""
    async with AsyncSessionLocal() as session:
        try:
            # Check if seed data already exists
            result = await session.execute(select(User).limit(1))
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print("✓ Seed data already exists. Skipping...")
                return
            
            print("Creating seed data...")
            
            # Create test user
            test_user = User(
                id=uuid4(),
                email="test@example.com"
            )
            session.add(test_user)
            await session.flush()
            
            print(f"✓ Created test user: {test_user.email} (ID: {test_user.id})")
            
            # Create Default Project for user
            default_project = UserProject(
                id=uuid4(),
                user_id=test_user.id,
                name="Default Project",
                workspace_path="/Users/test/projects/default"
            )
            session.add(default_project)
            await session.flush()
            
            print(f"✓ Created default project: {default_project.name} (ID: {default_project.id})")
            
            # Initialize Default Starter Pack for the project
            agents = await initialize_starter_pack(session, test_user.id, default_project.id)
            
            for agent in agents:
                print(f"✓ Created agent: {agent.name} (ID: {agent.id}) in project '{default_project.name}'")
            
            await session.commit()
            print("\n✓ Seed data created successfully!")
            print(f"\nTest user credentials:")
            print(f"  Email: {test_user.email}")
            print(f"  User ID: {test_user.id}")
            print(f"\nDefault Project:")
            print(f"  Project ID: {default_project.id}")
            print(f"  Project Name: {default_project.name}")
            print(f"  Agents Count: {len(agents)}")
            print(f"\nYou can generate a JWT token using:")
            print(f"  python scripts/generate_test_jwt.py {test_user.id}")
            
        except Exception as e:
            await session.rollback()
            print(f"✗ Error creating seed data: {e}")
            raise


async def init_database() -> None:
    """Initialize database schema and seed data."""
    try:
        print("Initializing database...")
        print(f"Database URL: {settings.database_url}")
        
        # Import all models to ensure they are registered
        from app.models import (  # noqa: F401
            ApprovalRequest,
            ChatSession,
            Message,
            Task,
            User,
            UserAgent,
            UserProject,
        )
        
        # Create tables
        from app.database import Base
        async with engine.begin() as conn:
            print("Creating database tables...")
            await conn.run_sync(Base.metadata.create_all)
            print("✓ Database tables created successfully!")
        
        # Create seed data
        await create_seed_data()
        
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        sys.exit(1)
    finally:
        await engine.dispose()


async def drop_all_tables() -> None:
    """Drop all tables (use with caution!)."""
    try:
        print("⚠️  WARNING: This will drop all tables and data!")
        response = input("Are you sure? Type 'yes' to confirm: ")
        
        if response.lower() != 'yes':
            print("Aborted.")
            return
        
        from app.database import Base
        async with engine.begin() as conn:
            print("Dropping all tables...")
            await conn.run_sync(Base.metadata.drop_all)
            print("✓ All tables dropped successfully!")
            
    except Exception as e:
        print(f"✗ Failed to drop tables: {e}")
        sys.exit(1)
    finally:
        await engine.dispose()


async def reset_database() -> None:
    """Reset database (drop and recreate)."""
    await drop_all_tables()
    await init_database()


def main() -> None:
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database initialization script")
    parser.add_argument(
        "action",
        choices=["init", "seed", "drop", "reset"],
        help="Action to perform: init (create tables), seed (add seed data), drop (drop all tables), reset (drop and recreate)"
    )
    
    args = parser.parse_args()
    
    if args.action == "init":
        asyncio.run(init_database())
    elif args.action == "seed":
        asyncio.run(create_seed_data())
    elif args.action == "drop":
        asyncio.run(drop_all_tables())
    elif args.action == "reset":
        asyncio.run(reset_database())


if __name__ == "__main__":
    main()
