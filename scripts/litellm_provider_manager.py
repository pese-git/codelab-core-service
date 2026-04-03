#!/usr/bin/env python3
"""
Скрипт для управления LLM провайдерами в LiteLLM через REST API.
Позволяет добавлять, удалять и просматривать провайдеры без перезагрузки сервиса.

Использование:
    python scripts/litellm_provider_manager.py add openai gpt-4-turbo-preview
    python scripts/litellm_provider_manager.py list
    python scripts/litellm_provider_manager.py test gpt-4-turbo-preview
"""

import asyncio
import json
import os
import sys
from typing import Optional
import httpx
from rich.console import Console
from rich.table import Table

console = Console()

# Конфигурация провайдеров
PROVIDERS_CONFIG = {
    "openai": {
        "model_list": {
            "gpt-4-turbo-preview": {
                "model_id": "gpt-4-turbo-preview",
                "api_key_env": "OPENAI_API_KEY",
            },
            "gpt-4": {
                "model_id": "gpt-4",
                "api_key_env": "OPENAI_API_KEY",
            },
            "gpt-3.5-turbo": {
                "model_id": "gpt-3.5-turbo",
                "api_key_env": "OPENAI_API_KEY",
            },
            "text-embedding-3-small": {
                "model_id": "text-embedding-3-small",
                "api_key_env": "OPENAI_API_KEY",
            },
            "text-embedding-3-large": {
                "model_id": "text-embedding-3-large",
                "api_key_env": "OPENAI_API_KEY",
            },
        },
    },
    "anthropic": {
        "model_list": {
            "claude-3-opus": {
                "model_id": "claude-3-opus-20240229",
                "api_key_env": "ANTHROPIC_API_KEY",
            },
            "claude-3-sonnet": {
                "model_id": "claude-3-sonnet-20240229",
                "api_key_env": "ANTHROPIC_API_KEY",
            },
            "claude-3-haiku": {
                "model_id": "claude-3-haiku-20240307",
                "api_key_env": "ANTHROPIC_API_KEY",
            },
        },
    },
    "cohere": {
        "model_list": {
            "cohere-command-r": {
                "model_id": "command-r-plus",
                "api_key_env": "COHERE_API_KEY",
            },
        },
    },
    "google": {
        "model_list": {
            "gemini-pro": {
                "model_id": "gemini-pro",
                "api_key_env": "GOOGLE_API_KEY",
            },
        },
    },
}


class LiteLLMProviderManager:
    def __init__(
        self,
        litellm_url: str = None,
        master_key: str = None,
    ):
        self.litellm_url = litellm_url or os.getenv(
            "CORE_SERVICE_LITELLM_URL", "http://localhost:4000"
        )
        self.master_key = master_key or os.getenv(
            "CORE_SERVICE_LITELLM_MASTER_KEY", "super-secret-key-change-in-production"
        )
        self.headers = {
            "Authorization": f"Bearer {self.master_key}",
            "Content-Type": "application/json",
        }

    async def add_provider(
        self,
        model_name: str,
        provider: str,
        model_id: str = None,
        api_key: str = None,
        **kwargs,
    ) -> bool:
        """Добавляет новый LLM провайдер."""
        if not api_key:
            console.print(
                f"[red]Ошибка: Не указан API ключ для {provider}[/red]"
            )
            return False

        if not model_id:
            model_id = model_name

        payload = {
            "model_name": model_name,
            "litellm_params": {
                "model": f"{provider}/{model_id}",
                "api_key": api_key,
            },
        }

        # Добавляем дополнительные параметры (api_base, api_version и т.д.)
        if kwargs:
            payload["litellm_params"].update(kwargs)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.litellm_url}/model/new",
                    json=payload,
                    headers=self.headers,
                )

            if response.status_code in [200, 201]:
                console.print(
                    f"[green]✅ Провайдер '{model_name}' успешно добавлен[/green]"
                )
                return True
            else:
                console.print(
                    f"[red]❌ Ошибка при добавлении провайдера: {response.text}[/red]"
                )
                return False
        except Exception as e:
            console.print(f"[red]❌ Ошибка подключения: {e}[/red]")
            return False

    async def list_providers(self) -> list:
        """Выводит список всех добавленных провайдеров."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.litellm_url}/models",
                    headers=self.headers,
                )

            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])

                if not models:
                    console.print("[yellow]ℹ️  Нет добавленных провайдеров[/yellow]")
                    return []

                table = Table(title="Зарегистрированные LLM модели")
                table.add_column("Имя модели", style="cyan")
                table.add_column("Провайдер", style="magenta")
                table.add_column("ID модели", style="green")

                for model in models:
                    model_name = model.get("model_name", "unknown")
                    litellm_params = model.get("litellm_params", {})
                    full_model = litellm_params.get("model", "unknown")

                    # Парсим provider/model_id
                    if "/" in full_model:
                        provider, model_id = full_model.split("/", 1)
                    else:
                        provider = "unknown"
                        model_id = full_model

                    table.add_row(model_name, provider, model_id)

                console.print(table)
                return models
            else:
                console.print(
                    f"[red]❌ Ошибка получения списка: {response.text}[/red]"
                )
                return []
        except Exception as e:
            console.print(f"[red]❌ Ошибка подключения: {e}[/red]")
            return []

    async def test_provider(
        self,
        model_name: str,
        message: str = "Hello, how are you?",
    ) -> bool:
        """Тестирует провайдер отправкой простого сообщения."""
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": message}],
            "max_tokens": 100,
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.litellm_url}/chat/completions",
                    json=payload,
                    headers=self.headers,
                )

            if response.status_code == 200:
                data = response.json()
                reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                console.print(f"[green]✅ Тест успешен![/green]")
                console.print(f"[cyan]Ответ:[/cyan] {reply[:100]}...")
                return True
            else:
                console.print(
                    f"[red]❌ Тест не пройден: {response.text}[/red]"
                )
                return False
        except Exception as e:
            console.print(f"[red]❌ Ошибка тестирования: {e}[/red]")
            return False

    async def add_predefined(self, provider_name: str) -> bool:
        """Добавляет все модели для известного провайдера."""
        if provider_name not in PROVIDERS_CONFIG:
            console.print(
                f"[red]Неизвестный провайдер: {provider_name}[/red]"
            )
            console.print(f"Доступные провайдеры: {', '.join(PROVIDERS_CONFIG.keys())}")
            return False

        config = PROVIDERS_CONFIG[provider_name]
        count = 0

        for model_name, model_config in config["model_list"].items():
            api_key_env = model_config.get("api_key_env")
            api_key = os.getenv(f"CORE_SERVICE_{api_key_env}")

            if not api_key:
                console.print(
                    f"[yellow]⚠️  Пропуск {model_name}: переменная {api_key_env} не установлена[/yellow]"
                )
                continue

            success = await self.add_provider(
                model_name=model_name,
                provider=provider_name,
                model_id=model_config.get("model_id", model_name),
                api_key=api_key,
            )

            if success:
                count += 1

        console.print(
            f"[green]📊 Добавлено моделей провайдера {provider_name}: {count}[/green]"
        )
        return count > 0


async def main():
    manager = LiteLLMProviderManager()

    if len(sys.argv) < 2:
        console.print("[cyan]Использование:[/cyan]")
        console.print("  python scripts/litellm_provider_manager.py list")
        console.print("  python scripts/litellm_provider_manager.py test <model_name>")
        console.print("  python scripts/litellm_provider_manager.py add-all <provider>")
        console.print("    Доступные провайдеры: openai, anthropic, cohere, google")
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        await manager.list_providers()

    elif command == "test" and len(sys.argv) >= 3:
        model_name = sys.argv[2]
        message = sys.argv[3] if len(sys.argv) >= 4 else "Hello, how are you?"
        await manager.test_provider(model_name, message)

    elif command == "add-all" and len(sys.argv) >= 3:
        provider = sys.argv[2]
        await manager.add_predefined(provider)

    else:
        console.print(f"[red]Неизвестная команда: {command}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
