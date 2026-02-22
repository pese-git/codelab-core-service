#!/usr/bin/env python3
"""Test script for orchestrator routing functionality."""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core.orchestrator_router import OrchestratorRouter
from app.models.user_agent import UserAgent
from app.models.user import User
from app.models.user_project import UserProject


async def test_orchestrator_router():
    """Test OrchestratorRouter with different message types."""
    
    # Create database connection
    engine = create_async_engine(str(settings.database_url), echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        try:
            # Get first project and user from database
            from sqlalchemy import select
            
            result = await db.execute(select(UserProject).limit(1))
            project = result.scalar_one_or_none()
            
            if not project:
                print("❌ No projects found in database")
                return
            
            user_id = project.user_id
            project_id = project.id
            
            print(f"✅ Using Project: {project.name} (ID: {project_id})")
            print(f"✅ Using User ID: {user_id}\n")
            
            # Initialize router
            router = OrchestratorRouter()
            
            # Test cases with different message types
            test_messages = [
                {
                    "message": "Напиши функцию для валидации email",
                    "expected_capability": "implement_feature",
                    "expected_agent": "Code",
                },
                {
                    "message": "Отладь баг в auth.py. Функция возвращает неправильное значение",
                    "expected_capability": "debug",
                    "expected_agent": "Debug",
                },
                {
                    "message": "Объясни как работает OAuth2 аутентификация",
                    "expected_capability": "explain",
                    "expected_agent": "Ask",
                },
                {
                    "message": "Спроектируй архитектуру нового микросервиса для обработки платежей",
                    "expected_capability": "design",
                    "expected_agent": "Architect",
                },
                {
                    "message": "Напиши unit тесты для функции калькулятора",
                    "expected_capability": "test",
                    "expected_agent": "Code",
                },
            ]
            
            print("=" * 80)
            print("TESTING ORCHESTRATOR ROUTING")
            print("=" * 80)
            
            for idx, test_case in enumerate(test_messages, 1):
                print(f"\n📝 Test Case {idx}:")
                print(f"   Message: {test_case['message'][:60]}...")
                print(f"   Expected: {test_case['expected_agent']} (capability: {test_case['expected_capability']})")
                
                try:
                    # Route the message
                    decision = await router.route_message(
                        db, user_id, project_id, test_case["message"]
                    )
                    
                    # Get agent details
                    agent_id = decision["selected_agent_id"]
                    agent_name = decision["agent_name"]
                    agent_role = decision["agent_role"]
                    routing_score = decision["routing_score"]
                    confidence = decision["confidence"]
                    required_caps = decision["required_capabilities"]
                    matched_caps = decision["matched_capabilities"]
                    
                    print(f"   ✅ Routing Decision:")
                    print(f"      - Agent: {agent_name} (role: {agent_role})")
                    print(f"      - Routing Score: {routing_score} ({confidence} confidence)")
                    print(f"      - Required Capabilities: {required_caps}")
                    print(f"      - Matched Capabilities: {matched_caps}")
                    
                    # Validate routing
                    if confidence == "high":
                        print(f"      ✅ HIGH CONFIDENCE routing (score >= 0.8)")
                    elif confidence == "medium":
                        print(f"      ⚠️  MEDIUM confidence routing (score >= 0.5)")
                    else:
                        print(f"      ⚠️  LOW confidence routing (fallback)")
                    
                except Exception as e:
                    print(f"   ❌ Error: {str(e)}")
            
            print("\n" + "=" * 80)
            print("ROUTING TESTS COMPLETED")
            print("=" * 80)
            
        except Exception as e:
            print(f"❌ Error during testing: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_orchestrator_router())
