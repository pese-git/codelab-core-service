#!/usr/bin/env python3
"""Initialize database before running migrations."""

import asyncio
import sys
from urllib.parse import urlparse

import asyncpg

async def create_database():
    """Create database if it doesn't exist."""
    db_url = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not db_url:
        print("ERROR: Database URL not provided")
        return False
    
    if "postgresql" not in db_url:
        # SQLite doesn't need pre-creation
        return True
    
    # Extract database name
    parsed = urlparse(db_url.replace("postgresql+asyncpg://", "postgresql://"))
    db_name = parsed.path.lstrip('/')
    
    if not db_name:
        print("ERROR: Could not extract database name from URL")
        return False
    
    try:
        # Connect to default postgres database
        conn = await asyncpg.connect(
            host=parsed.hostname or 'localhost',
            port=parsed.port or 5432,
            user=parsed.username or 'postgres',
            password=parsed.password or 'postgres',
            database='postgres'
        )
        
        try:
            # Check if database exists
            exists = await conn.fetchval(
                f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"
            )
            if not exists:
                print(f"Creating database '{db_name}'...")
                await conn.execute(f'CREATE DATABASE "{db_name}"')
                print(f"Database '{db_name}' created successfully")
            else:
                print(f"Database '{db_name}' already exists")
        finally:
            await conn.close()
        
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == '__main__':
    success = asyncio.run(create_database())
    sys.exit(0 if success else 1)
