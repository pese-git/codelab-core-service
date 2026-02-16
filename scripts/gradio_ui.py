#!/usr/bin/env python3
"""
Gradio клиент для взаимодействия с Personal Multi-Agent AI Platform.

Использование:
    python scripts/gradio_client.py

Требования:
    - Запущенный сервис на http://localhost:8000
    - JWT токен (можно сгенерировать через scripts/generate_test_jwt.py)
"""

import asyncio
import json
import os
from datetime import datetime
from typing import List, Tuple, Optional
import httpx
import gradio as gr
from queue import Queue
import threading


# Конфигурация
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DEFAULT_JWT = os.getenv("JWT_TOKEN", "")
GRADIO_PORT = int(os.getenv("GRADIO_SERVER_PORT", "7860"))


class PersonalAIClient:
    """Клиент для взаимодействия с Personal AI Platform."""
    
    def __init__(self, base_url: str, jwt_token: str):
        self.base_url = base_url
        self.jwt_token = jwt_token
        self.headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
        self.event_queue = Queue()
        self.stream_task = None
        self.current_session_id = None
        
    async def create_agent(self, name: str, system_prompt: str,
                          provider: str = "openai", model: str = "gpt-4o-mini",
                          temperature: float = 0.7) -> dict:
        """Создать нового агента."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/my/agents/",
                headers=self.headers,
                json={
                    "name": name,
                    "system_prompt": system_prompt,
                    "model": model,
                    "tools": [],
                    "temperature": temperature,
                    "concurrency_limit": 3,
                    "max_tokens": 4096
                },
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def list_agents(self) -> List[dict]:
        """Получить список агентов."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/my/agents/",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            # API возвращает объект с полем "agents"
            if isinstance(data, dict) and "agents" in data:
                return data["agents"]
            return data if isinstance(data, list) else []
    
    async def delete_agent(self, agent_id: str) -> dict:
        """Удалить агента."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/my/agents/{agent_id}/",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def create_session(self) -> dict:
        """Создать новую чат-сессию."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/my/chat/sessions/",
                headers=self.headers,
                json={},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def list_sessions(self) -> List[dict]:
        """Получить список сессий."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/my/chat/sessions/",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            # API может возвращать объект с полем "sessions" или список
            if isinstance(data, dict) and "sessions" in data:
                return data["sessions"]
            return data if isinstance(data, list) else []
    
    async def send_message(self, session_id: str, content: str,
                          target_agent: Optional[str] = None) -> dict:
        """Отправить сообщение в чат."""
        payload = {"content": content}
        if target_agent:
            payload["target_agent"] = target_agent
            
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/my/chat/{session_id}/message/",
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def get_chat_history(self, session_id: str) -> List[dict]:
        """Получить историю чата."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/my/chat/sessions/{session_id}/messages/",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            # API возвращает объект с полем "messages"
            if isinstance(data, dict) and "messages" in data:
                return data["messages"]
            return data if isinstance(data, list) else []
    
    async def listen_stream_events(self, session_id: str):
        """Слушать streaming события для сессии (NDJSON формат)."""
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "GET",
                    f"{self.base_url}/my/chat/{session_id}/events/",
                    headers=self.headers,
                    timeout=None,
                ) as response:
                    # Читаем NDJSON (Newline Delimited JSON)
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if line:  # Пропускаем пустые строки
                            try:
                                data = json.loads(line)
                                self.event_queue.put(data)
                            except json.JSONDecodeError as e:
                                print(f"JSON decode error: {e}, line: {line}")
        except Exception as e:
            self.event_queue.put({"error": str(e)})
    
    # Backward compatibility alias
    async def listen_sse_events(self, session_id: str):
        """Deprecated: используйте listen_stream_events."""
        return await self.listen_stream_events(session_id)


# Глобальный клиент
client: Optional[PersonalAIClient] = None


def initialize_client(jwt_token: str) -> str:
    """Инициализировать клиент с JWT токеном."""
    global client
    if not jwt_token:
        return "❌ Ошибка: JWT токен не может быть пустым"
    
    try:
        client = PersonalAIClient(API_BASE_URL, jwt_token)
        return f"✅ Клиент инициализирован\n🔗 API: {API_BASE_URL}"
    except Exception as e:
        return f"❌ Ошибка инициализации: {str(e)}"


def create_agent_ui(name: str, system_prompt: str, provider: str, model: str) -> str:
    """UI функция для создания агента."""
    if not client:
        return "❌ Сначала инициализируйте клиент с JWT токеном"
    
    try:
        result = asyncio.run(client.create_agent(name, system_prompt, provider, model))
        return f"✅ Агент создан:\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"


def list_agents_ui() -> str:
    """UI функция для получения списка агентов."""
    if not client:
        return "❌ Сначала инициализируйте клиент с JWT токеном"
    
    try:
        agents = asyncio.run(client.list_agents())
        if not agents:
            return "📋 Агенты не найдены"
        
        result = "📋 **Список агентов:**\n\n"
        for agent in agents:
            # API возвращает 'id', а не 'agent_id'
            agent_id = agent.get('id', 'N/A')
            name = agent.get('name', 'N/A')
            status = agent.get('status', 'N/A')
            # config.model - это строка, а не объект
            model = agent.get('config', {}).get('model', 'N/A')
            
            result += f"- **{name}** (`{agent_id}`)\n"
            result += f"  - Статус: {status}\n"
            result += f"  - Модель: {model}\n\n"
        return result
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"


def delete_agent_ui(agent_id: str) -> str:
    """UI функция для удаления агента."""
    if not client:
        return "❌ Сначала инициализируйте клиент с JWT токеном"
    
    if not agent_id:
        return "❌ Укажите agent_id"
    
    try:
        result = asyncio.run(client.delete_agent(agent_id))
        return f"✅ Агент удален:\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"


def create_session_ui() -> str:
    """UI функция для создания сессии."""
    if not client:
        return "❌ Сначала инициализируйте клиент с JWT токеном"
    
    try:
        result = asyncio.run(client.create_session())
        session_id = result.get('id')
        client.current_session_id = session_id
        return f"✅ Сессия создана:\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```\n\n💡 Session ID: **{session_id}**"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"


def list_sessions_ui() -> str:
    """UI функция для получения списка сессий."""
    if not client:
        return "❌ Сначала инициализируйте клиент с JWT токеном"
    
    try:
        sessions = asyncio.run(client.list_sessions())
        if not sessions:
            return "📋 Сессии не найдены"
        
        result = "📋 **Список сессий:**\n\n"
        for session in sessions:
            result += f"- **Session {session.get('id')}**\n"
            result += f"  - Создана: {session.get('created_at', 'N/A')}\n"
            result += f"  - Сообщений: {session.get('message_count', 0)}\n\n"
        return result
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"


def send_message_ui(session_id: str, message: str, target_agent: str) -> Tuple[str, str]:
    """UI функция для отправки сообщения."""
    if not client:
        return "❌ Сначала инициализируйте клиент с JWT токеном", ""
    
    if not session_id:
        return "❌ Укажите Session ID", ""
    
    if not message:
        return "❌ Сообщение не может быть пустым", ""
    
    try:
        # session_id - это UUID строка, не int
        target = target_agent if target_agent else None
        
        result = asyncio.run(client.send_message(session_id, message, target))
        
        # Запустить SSE listener в фоне
        if client.current_session_id != session_id:
            client.current_session_id = session_id
            # Очистить очередь событий
            while not client.event_queue.empty():
                client.event_queue.get()
        
        response = f"✅ Сообщение отправлено:\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"
        
        # Получить историю чата
        history = asyncio.run(client.get_chat_history(session_id))
        chat_display = format_chat_history(history)
        
        return response, chat_display
    except Exception as e:
        return f"❌ Ошибка: {str(e)}", ""


def format_chat_history(history: List[dict]) -> str:
    """Форматировать историю чата для отображения."""
    if not history:
        return "💬 История чата пуста"
    
    result = "💬 **История чата:**\n\n"
    for msg in history:
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        timestamp = msg.get('created_at', '')
        
        if role == 'user':
            result += f"👤 **Пользователь** ({timestamp}):\n{content}\n\n"
        elif role == 'assistant':
            # API может не возвращать agent_id в некоторых случаях
            agent_id = msg.get('agent_id', msg.get('metadata', {}).get('agent_id', 'N/A'))
            result += f"🤖 **Агент** `{agent_id}` ({timestamp}):\n{content}\n\n"
        else:
            result += f"❓ **{role}** ({timestamp}):\n{content}\n\n"
    
    return result


def get_chat_history_ui(session_id: str) -> str:
    """UI функция для получения истории чата."""
    if not client:
        return "❌ Сначала инициализируйте клиент с JWT токеном"
    
    if not session_id:
        return "❌ Укажите Session ID"
    
    try:
        # session_id - это UUID строка, не int
        history = asyncio.run(client.get_chat_history(session_id))
        return format_chat_history(history)
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"


def start_sse_listener_ui(session_id: str) -> str:
    """UI функция для запуска streaming listener."""
    if not client:
        return "❌ Сначала инициализируйте клиент с JWT токеном"
    
    if not session_id:
        return "❌ Укажите Session ID"
    
    try:
        # session_id - это UUID строка, не int
        
        # Запустить streaming listener в отдельном потоке
        def run_stream():
            asyncio.run(client.listen_stream_events(session_id))

        thread = threading.Thread(target=run_stream, daemon=True)
        thread.start()
        
        return f"✅ Streaming listener запущен для сессии {session_id}\n\n💡 События будут отображаться ниже"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"


def get_sse_events_ui() -> str:
    """UI функция для получения streaming событий."""
    if not client:
        return "❌ Сначала инициализируйте клиент с JWT токеном"
    
    events = []
    while not client.event_queue.empty():
        events.append(client.event_queue.get())
    
    if not events:
        return "⏳ Ожидание событий..."
    
    result = "📡 **Streaming События:**\n\n"
    for event in events:
        if "error" in event:
            result += f"❌ Ошибка: {event['error']}\n\n"
        else:
            event_type = event.get('event_type', 'unknown')
            timestamp = event.get('timestamp', '')
            payload = event.get('payload', {})
            
            result += f"🔔 **{event_type}** ({timestamp})\n"
            result += f"```json\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n```\n\n"
    
    return result


# Создание Gradio интерфейса
def create_gradio_app():
    """Создать Gradio приложение."""
    
    with gr.Blocks(title="Personal AI Platform Client") as app:
        gr.Markdown("""
        # 🤖 Personal Multi-Agent AI Platform
        ## Gradio клиент для взаимодействия с сервисом
        
        **Документация:** [REST API](../doc/rest-api.md) | [Streaming API](../doc/streaming-fetch-api.md)
        """)
        
        # Секция инициализации
        with gr.Tab("🔐 Инициализация"):
            gr.Markdown("### Настройка подключения")
            jwt_input = gr.Textbox(
                label="JWT Token",
                placeholder="Вставьте JWT токен...",
                value=DEFAULT_JWT,
                type="password",
                lines=3
            )
            init_btn = gr.Button("🚀 Инициализировать клиент", variant="primary")
            init_output = gr.Markdown()
            
            init_btn.click(
                fn=initialize_client,
                inputs=[jwt_input],
                outputs=[init_output]
            )
        
        # Секция управления агентами
        with gr.Tab("👥 Агенты"):
            gr.Markdown("### Управление агентами")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("#### Создать агента")
                    agent_name = gr.Textbox(label="Имя агента", placeholder="Мой помощник")
                    agent_prompt = gr.Textbox(
                        label="System Prompt",
                        placeholder="Ты опытный программист...",
                        lines=5
                    )
                    agent_provider = gr.Dropdown(
                        label="Provider",
                        choices=["openai", "anthropic", "local"],
                        value="openai"
                    )
                    agent_model = gr.Textbox(label="Model", value="gpt-4o-mini")
                    create_agent_btn = gr.Button("➕ Создать агента", variant="primary")
                    create_agent_output = gr.Markdown()
                
                with gr.Column():
                    gr.Markdown("#### Список агентов")
                    list_agents_btn = gr.Button("📋 Обновить список")
                    list_agents_output = gr.Markdown()
                    
                    gr.Markdown("#### Удалить агента")
                    delete_agent_id = gr.Textbox(label="Agent ID", placeholder="user123_agent_v1")
                    delete_agent_btn = gr.Button("🗑️ Удалить агента", variant="stop")
                    delete_agent_output = gr.Markdown()
            
            create_agent_btn.click(
                fn=create_agent_ui,
                inputs=[agent_name, agent_prompt, agent_provider, agent_model],
                outputs=[create_agent_output]
            )
            
            list_agents_btn.click(
                fn=list_agents_ui,
                outputs=[list_agents_output]
            )
            
            delete_agent_btn.click(
                fn=delete_agent_ui,
                inputs=[delete_agent_id],
                outputs=[delete_agent_output]
            )
        
        # Секция чата
        with gr.Tab("💬 Чат"):
            gr.Markdown("### Чат с агентами")
            
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("#### Управление сессиями")
                    create_session_btn = gr.Button("➕ Создать сессию", variant="primary")
                    create_session_output = gr.Markdown()
                    
                    list_sessions_btn = gr.Button("📋 Список сессий")
                    list_sessions_output = gr.Markdown()
                
                with gr.Column(scale=2):
                    gr.Markdown("#### Отправить сообщение")
                    chat_session_id = gr.Textbox(label="Session ID", placeholder="1")
                    chat_message = gr.Textbox(
                        label="Сообщение",
                        placeholder="Привет! Помоги мне...",
                        lines=3
                    )
                    chat_target_agent = gr.Textbox(
                        label="Target Agent (опционально)",
                        placeholder="user123_agent_v1"
                    )
                    send_message_btn = gr.Button("📤 Отправить", variant="primary")
                    send_message_output = gr.Markdown()
                    
                    gr.Markdown("#### История чата")
                    get_history_btn = gr.Button("🔄 Обновить историю")
                    chat_history_output = gr.Markdown()
            
            create_session_btn.click(
                fn=create_session_ui,
                outputs=[create_session_output]
            )
            
            list_sessions_btn.click(
                fn=list_sessions_ui,
                outputs=[list_sessions_output]
            )
            
            send_message_btn.click(
                fn=send_message_ui,
                inputs=[chat_session_id, chat_message, chat_target_agent],
                outputs=[send_message_output, chat_history_output]
            )
            
            get_history_btn.click(
                fn=get_chat_history_ui,
                inputs=[chat_session_id],
                outputs=[chat_history_output]
            )
        
        # Секция Streaming событий
        with gr.Tab("📡 Streaming События"):
            gr.Markdown("### Real-time события (NDJSON)")

            sse_session_id = gr.Textbox(label="Session ID", placeholder="1")
            start_sse_btn = gr.Button("▶️ Запустить Streaming listener", variant="primary")
            start_sse_output = gr.Markdown()
            
            gr.Markdown("#### События")
            get_events_btn = gr.Button("🔄 Обновить события")
            events_output = gr.Markdown()
            
            start_sse_btn.click(
                fn=start_sse_listener_ui,
                inputs=[sse_session_id],
                outputs=[start_sse_output]
            )
            
            get_events_btn.click(
                fn=get_sse_events_ui,
                outputs=[events_output]
            )
        
        # Информация
        with gr.Tab("ℹ️ Информация"):
            gr.Markdown(f"""
            ### Конфигурация
            
            - **API Base URL:** `{API_BASE_URL}`
            - **Документация:** `/docs` (Swagger UI)
            - **Health Check:** `/health`
            
            ### Быстрый старт
            
            1. **Инициализация:** Вставьте JWT токен и нажмите "Инициализировать клиент"
            2. **Создать агента:** Перейдите на вкладку "Агенты" и создайте своего первого агента
            3. **Создать сессию:** На вкладке "Чат" создайте новую сессию
            4. **Отправить сообщение:** Введите Session ID и отправьте сообщение
            5. **Streaming События:** Запустите Streaming listener для получения real-time событий
            
            ### Генерация JWT токена
            
            ```bash
            python scripts/generate_test_jwt.py
            ```
            
            ### Переменные окружения
            
            ```bash
            export API_BASE_URL="http://localhost:8000"
            export JWT_TOKEN="your_jwt_token_here"
            ```
            
            ### Типы Streaming событий
            
            - `direct_agent_call` - Прямой вызов агента
            - `agent_status_changed` - Изменение статуса агента
            - `task_plan_created` - Создан план задач
            - `task_started` - Задача начата
            - `task_progress` - Прогресс выполнения
            - `task_completed` - Задача завершена
            - `tool_request` - Запрос на подтверждение tool
            - `approval_required` - Требуется подтверждение
            - `context_retrieved` - Получен RAG контекст
            """)
    
    return app


if __name__ == "__main__":
    app = create_gradio_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=GRADIO_PORT,
        share=False,
        show_error=True
    )
