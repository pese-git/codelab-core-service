.PHONY: help install dev up down logs clean test lint format migrate seed reset

# Цвета для вывода
GREEN  := \033[0;32m
YELLOW := \033[0;33m
NC     := \033[0m # No Color

help: ## Показать эту справку
	@echo "$(GREEN)CodeLab Core Service - Команды разработки$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

install: ## Установить зависимости проекта
	@echo "$(GREEN)Установка зависимостей...$(NC)"
	uv pip install -e .

dev: ## Запустить dev окружение (без мониторинга)
	@echo "$(GREEN)Запуск dev окружения...$(NC)"
	docker-compose -f docker-compose.dev.yml up -d
	@echo "$(GREEN)✓ Сервисы запущены!$(NC)"
	@echo "API: http://localhost:8000"
	@echo "Docs: http://localhost:8000/my/docs"

up: ## Запустить полный стек (с мониторингом)
	@echo "$(GREEN)Запуск полного стека...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Все сервисы запущены!$(NC)"
	@echo "API: http://localhost:8000"
	@echo "Docs: http://localhost:8000/my/docs"
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana: http://localhost:3000 (admin/admin)"

down: ## Остановить все сервисы
	@echo "$(YELLOW)Остановка сервисов...$(NC)"
	docker-compose down
	docker-compose -f docker-compose.dev.yml down
	@echo "$(GREEN)✓ Сервисы остановлены$(NC)"

logs: ## Показать логи приложения
	docker-compose logs -f app

logs-all: ## Показать логи всех сервисов
	docker-compose logs -f

ps: ## Показать статус сервисов
	@docker-compose ps

clean: ## Остановить сервисы и удалить volumes (УДАЛИТ ВСЕ ДАННЫЕ!)
	@echo "$(YELLOW)⚠️  ВНИМАНИЕ: Это удалит все данные!$(NC)"
	@read -p "Продолжить? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		docker-compose -f docker-compose.dev.yml down -v; \
		echo "$(GREEN)✓ Volumes удалены$(NC)"; \
	else \
		echo "Отменено"; \
	fi

test: ## Запустить тесты
	@echo "$(GREEN)Запуск тестов...$(NC)"
	pytest

test-cov: ## Запустить тесты с покрытием
	@echo "$(GREEN)Запуск тестов с покрытием...$(NC)"
	pytest --cov=app --cov-report=html --cov-report=term

lint: ## Проверить код линтером
	@echo "$(GREEN)Проверка кода...$(NC)"
	ruff check .

format: ## Форматировать код
	@echo "$(GREEN)Форматирование кода...$(NC)"
	ruff format .

type-check: ## Проверить типы
	@echo "$(GREEN)Проверка типов...$(NC)"
	mypy app/

migrate: ## Применить миграции базы данных
	@echo "$(GREEN)Применение миграций...$(NC)"
	alembic upgrade head
	@echo "$(GREEN)✓ Миграции применены$(NC)"

migrate-create: ## Создать новую миграцию (использование: make migrate-create MSG="описание")
	@if [ -z "$(MSG)" ]; then \
		echo "$(YELLOW)Использование: make migrate-create MSG=\"описание миграции\"$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Создание миграции: $(MSG)$(NC)"
	alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Откатить последнюю миграцию
	@echo "$(YELLOW)Откат последней миграции...$(NC)"
	alembic downgrade -1
	@echo "$(GREEN)✓ Миграция откачена$(NC)"

seed: ## Добавить seed data в базу данных
	@echo "$(GREEN)Добавление seed data...$(NC)"
	python scripts/init_db.py seed
	@echo "$(GREEN)✓ Seed data добавлены$(NC)"

init-db: ## Инициализировать базу данных (создать таблицы + seed data)
	@echo "$(GREEN)Инициализация базы данных...$(NC)"
	python scripts/init_db.py init
	@echo "$(GREEN)✓ База данных инициализирована$(NC)"

reset-db: ## Сбросить базу данных (УДАЛИТ ВСЕ ДАННЫЕ!)
	@echo "$(YELLOW)⚠️  ВНИМАНИЕ: Это удалит все данные из базы!$(NC)"
	@read -p "Продолжить? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		python scripts/init_db.py reset; \
		echo "$(GREEN)✓ База данных сброшена$(NC)"; \
	else \
		echo "Отменено"; \
	fi

shell: ## Открыть shell в контейнере приложения
	docker-compose exec app /bin/sh

db-shell: ## Открыть psql shell в PostgreSQL
	docker-compose exec postgres psql -U postgres -d codelab

redis-cli: ## Открыть redis-cli
	docker-compose exec redis redis-cli

health: ## Проверить health endpoint
	@curl -s http://localhost:8000/health | python -m json.tool

env: ## Создать .env файл из примера
	@if [ -f .env ]; then \
		echo "$(YELLOW).env файл уже существует$(NC)"; \
	else \
		cp .env.example .env; \
		echo "$(GREEN)✓ .env файл создан из .env.example$(NC)"; \
		echo "$(YELLOW)Не забудьте установить OPENAI_API_KEY и JWT_SECRET_KEY!$(NC)"; \
	fi

# Комбинированные команды
setup: env dev migrate seed ## Полная настройка проекта (env + dev + migrate + seed)
	@echo ""
	@echo "$(GREEN)✓ Проект настроен и готов к работе!$(NC)"
	@echo ""
	@echo "Следующие шаги:"
	@echo "  1. Отредактируйте .env и установите OPENAI_API_KEY"
	@echo "  2. Перезапустите сервисы: make down && make dev"
	@echo "  3. Откройте API docs: http://localhost:8000/my/docs"

restart: down dev ## Перезапустить dev окружение
	@echo "$(GREEN)✓ Сервисы перезапущены$(NC)"

rebuild: ## Пересобрать и перезапустить контейнеры
	@echo "$(GREEN)Пересборка контейнеров...$(NC)"
	docker-compose build --no-cache
	docker-compose up -d
	@echo "$(GREEN)✓ Контейнеры пересобраны и запущены$(NC)"
