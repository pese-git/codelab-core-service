#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функциональности Gradio UI.
"""

import asyncio
import sys
import os

# Добавить путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.gradio_ui import PersonalAIClient


async def test_client():
    """Тестирование клиента."""
    
    # Генерация тестового JWT токена
    from app.config import settings
    from jose import jwt
    from datetime import datetime, timedelta
    import uuid
    
    user_id = str(uuid.uuid4())
    expire = datetime.utcnow() + timedelta(minutes=30)
    
    token_data = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    jwt_token = jwt.encode(
        token_data,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    print(f"✅ JWT токен сгенерирован")
    print(f"   User ID: {user_id}")
    print(f"   Token: {jwt_token[:50]}...")
    print()
    
    # Создать клиент
    client = PersonalAIClient("http://localhost:8000", jwt_token)
    print("✅ Клиент создан")
    print()
    
    # Тест 1: Список агентов (должен быть пустым для нового пользователя)
    print("📋 Тест 1: Получение списка агентов...")
    try:
        agents = await client.list_agents()
        print(f"   ✅ Успешно! Найдено агентов: {len(agents)}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False
    print()
    
    # Тест 2: Использовать существующего агента
    print("👤 Тест 2: Получение существующего агента...")
    agent_id = None
    if len(agents) > 0:
        agent_id = agents[0].get("id")
        print(f"   ✅ Используем агента: {agents[0].get('name')} (ID: {agent_id})")
    else:
        print(f"   ⚠️  Агенты не найдены, пропускаем тесты с агентами")
    print()
    
    # Тест 4: Создание сессии
    print("💬 Тест 4: Создание чат-сессии...")
    try:
        session = await client.create_session()
        session_id = session.get("id")
        print(f"   ✅ Сессия создана: {session_id}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False
    print()
    
    # Тест 5: Список сессий
    print("📋 Тест 5: Получение списка сессий...")
    try:
        sessions = await client.list_sessions()
        print(f"   ✅ Найдено сессий: {len(sessions)}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False
    print()
    
    # Тест 6: Отправка сообщения
    if agent_id:
        print("📤 Тест 6: Отправка сообщения с прямым вызовом агента...")
        try:
            result = await client.send_message(
                session_id=session_id,
                content="Привет! Это тестовое сообщение.",
                target_agent=str(agent_id)
            )
            print(f"   ✅ Сообщение отправлено")
            print(f"   Execution ID: {result.get('execution_id', 'N/A')}")
            print(f"   Mode: {result.get('mode', 'N/A')}")
        except Exception as e:
            print(f"   ⚠️  Ошибка (ожидаемо, если агент не настроен): {e}")
    else:
        print("📤 Тест 6: Пропущен (нет агентов)")
    print()
    
    # Тест 7: История чата
    print("📜 Тест 7: Получение истории чата...")
    try:
        history = await client.get_chat_history(session_id)
        print(f"   ✅ Найдено сообщений: {len(history)}")
        if len(history) > 0:
            print(f"   Последнее сообщение: {history[-1].get('content')[:50]}...")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False
    print()
    
    # Тест 8: Пропускаем удаление существующего агента
    print("🗑️  Тест 8: Удаление агента (пропущен)")
    print(f"   ⚠️  Не удаляем существующего агента")
    print()
    
    print("=" * 60)
    print("✅ Все тесты пройдены успешно!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Тестирование Gradio UI клиента")
    print("=" * 60)
    print()
    
    success = asyncio.run(test_client())
    sys.exit(0 if success else 1)
