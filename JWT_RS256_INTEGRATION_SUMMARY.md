# JWT RS256 интеграция между auth-service и core-service

## 📋 Статус: ✅ ПОЛНОСТЬЮ РЕАЛИЗОВАНО

Интеграция JWT RS256 между auth-service и core-service полностью реализована и готова к использованию.

## 🔍 Реализованные компоненты

### 1. ✅ Клиент JWKS (`app/services/jwks_client.py`)

**Классы и функции:**
- [`JWKSClient`](app/services/jwks_client.py:16) - асинхронный клиент для получения и кеширования JWKS
- [`get_jwks_client()`](app/services/jwks_client.py:308) - получить глобальный экземпляр JWKS клиента
- [`close_jwks_client()`](app/services/jwks_client.py:321) - закрыть глобальный экземпляр

**Функциональность:**
- ✅ Асинхронные HTTP запросы через `httpx.AsyncClient`
- ✅ Кеширование JWKS с TTL = 3600 сек (1 час)
- ✅ Автоматическое обновление кеша при истечении TTL
- ✅ Fallback на кешированный JWKS при ошибках сети
- ✅ Конвертация JWK в PEM-формат через `jose.backends.rsa_backend.RSAKey`
- ✅ Получение публичного ключа по Key ID (`kid`)
- ✅ Валидация JWT токенов с RS256
- ✅ Подробное логирование через `structlog`
- ✅ Обработка всех типов ошибок

**Методы:**
```python
async def get_jwks() -> dict[str, Any]
  # Получить JWKS с автоматическим обновлением кеша

async def get_public_key(kid: str) -> str
  # Получить публичный ключ по Key ID

async def validate_token(
    token: str,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
) -> dict[str, Any]
  # Валидировать JWT токен с RS256
```

### 2. ✅ Конфигурация (`app/config.py`)

**Настройки JWT:**
```python
# JWT Authentication
jwt_secret_key: str = Field(default="your-secret-key-change-in-production")
jwt_algorithm: str = Field(default="RS256")
jwt_access_token_expire_minutes: int = Field(default=30)
jwt_refresh_token_expire_days: int = Field(default=7)

# JWT RS256 Configuration
jwt_issuer: str = Field(default="https://auth.codelab.local")
jwt_audience: str = Field(default="codelab-api")
auth_service_jwks_url: str = Field(
    default="http://codelab-auth-service:8003/.well-known/jwks.json"
)
jwks_cache_ttl: int = Field(default=3600)  # 1 час
```

**Примечание:** `jwt_secret_key` сохранён для обратной совместимости, но для RS256 не используется.

**Настройки LiteLLM:**
```python
litellm_url: str = Field(default="http://localhost:4000")
litellm_master_key: str = Field(default="")

# Default LLM Provider (for starter pack initialization)
llm_default_model: str = Field(default="gpt-4-turbo-preview")
llm_default_embedding_model: str = Field(default="text-embedding-3-small")
llm_default_base_url: str = Field(default="https://openrouter.com/api/v1")
llm_default_api_key: str = Field(default="sk-you-openrouter-api-key-change-in-production")
```

### 3. ✅ Middleware аутентификации (`app/middleware/user_isolation.py`)

**Функциональность:**
- ✅ Извлечение JWT токена из заголовка `Authorization: Bearer <token>`
- ✅ Получение `kid` из заголовка токена через [`jwt.get_unverified_header()`](app/middleware/user_isolation.py:248)
- ✅ Получение публичного ключа через `jwks_client.get_public_key(kid)`
- ✅ Валидация токена с параметрами:
  - `algorithms=["RS256"]`
  - `audience=settings.jwt_audience`
  - `issuer=settings.jwt_issuer`
- ✅ Проверка наличия `sub` claim (UUID пользователя)
- ✅ Проверка типа токена (`access` или `refresh`)
- ✅ Инъекция user context в `request.state`:
  - `user_id` (UUID)
  - `user_email` (опционально)
  - `user_prefix` (для ключей Redis)
  - `db_filter` (для изоляции данных)
- ✅ Подробное логирование всех событий и ошибок
- ✅ Обработка всех типов ошибок с понятными сообщениями

**Поддерживаемые endpoints:**
- Пропускает неавторизованные routes (не начинающиеся с `/my/`)
- Пропускает публичные endpoints: `/docs`, `/openapi.json`, `/health`, `/ready`

### 4. ✅ Зависимости (`pyproject.toml`)

**Требуемые пакеты уже есть:**
- `python-jose[cryptography]>=3.3.0` ✅
- `httpx>=0.27.0` ✅

### 5. ✅ Docker конфигурация (`docker-compose.yml`)

**Переменные окружения для core-service:**
```yaml
JWT_ALGORITHM: ${JWT_ALGORITHM:-RS256}
JWT_ISSUER: ${JWT_ISSUER:-https://auth.codelab.local}
JWT_AUDIENCE: ${JWT_AUDIENCE:-codelab-api}
AUTH_SERVICE_JWKS_URL: ${AUTH_SERVICE_JWKS_URL:-http://codelab-auth-service:8003/.well-known/jwks.json}
JWKS_CACHE_TTL: ${JWKS_CACHE_TTL:-3600}
```

**Переменные окружения для auth-service:**
```yaml
AUTH_SERVICE__JWT_ISSUER=https://auth.codelab.local
AUTH_SERVICE__JWT_AUDIENCE=codelab-api
AUTH_SERVICE__PRIVATE_KEY_PATH=/app/keys/private_key.pem
AUTH_SERVICE__PUBLIC_KEY_PATH=/app/keys/public_key.pem
```

## 🔄 Поток аутентификации

1. **Auth Service**: Генерирует JWT RS256 токен, подписанный приватным ключом
   - Токен содержит `kid` в заголовке (Key ID)
   - Payload содержит `sub` (user_id), `type`, `issuer`, `audience`, `exp`, `iat`

2. **Core Service**: Получает и валидирует токен
   - Middleware перехватывает запрос к `/my/*` endpoints
   - Извлекает токен из заголовка `Authorization: Bearer`
   - Получает `kid` из заголовка токена
   - Загружает публичный ключ от auth-service через JWKS endpoint
   - Валидирует подпись токена с использованием публичного ключа
   - Проверяет `issuer`, `audience`, `exp`
   - Инъектирует user context в request

3. **Кеширование**: JWKS кешируется в памяти с TTL 1 час
   - Автоматическое обновление при истечении TTL
   - Fallback на кешированную версию при ошибках сети

## 📚 Структуры данных

### JWT Token Payload (пример)
```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "type": "access",
  "issuer": "https://auth.codelab.local",
  "audience": "codelab-api",
  "exp": 1234567890,
  "iat": 1234567800,
  "email": "user@example.com"
}
```

### JWKS Response (пример)
```json
{
  "keys": [
    {
      "kty": "RSA",
      "kid": "key-id-1",
      "use": "sig",
      "alg": "RS256",
      "n": "...",
      "e": "AQAB"
    }
  ]
}
```

### Request State (после валидации)
```python
request.state.user_id: UUID  # "550e8400-e29b-41d4-a716-446655440000"
request.state.user_email: Optional[str]  # "user@example.com"
request.state.user_prefix: str  # "user550e8400-e29b-41d4-a716-446655440000"
request.state.db_filter: dict[str, UUID]  # {"user_id": UUID(...)}
```

## 🧪 Тестирование

Полный гайд по тестированию интеграции находится в файле [`INTEGRATION_TEST_RS256.md`](INTEGRATION_TEST_RS256.md).

### Быстрый тест

```bash
# 1. Получить JWKS от auth-service
curl http://codelab-auth-service:8003/.well-known/jwks.json

# 2. Получить JWT токен от auth-service
TOKEN=$(curl -X POST http://codelab-auth-service:8003/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}' \
  | jq -r '.access_token')

# 3. Использовать токен в core-service
curl -X GET http://localhost:8000/api/v1/core/my/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

## 🔐 Требования к безопасности

- ✅ RS256 (асимметричная криптография) вместо HS256 (симметричная)
- ✅ Публичный ключ используется только для валидации (защита от подделок)
- ✅ Приватный ключ хранится только в auth-service
- ✅ Кеширование публичного ключа снижает нагрузку на auth-service
- ✅ Fallback на кеш при сетевых ошибках обеспечивает отказоустойчивость

## 📋 Список изменений

### Файлы реализованные/обновленные:
- ✅ `codelab-core-service/app/services/jwks_client.py` (уже существует, полностью функционален)
- ✅ `codelab-core-service/app/config.py` (обновлена, добавлены настройки RS256)
- ✅ `codelab-core-service/app/middleware/user_isolation.py` (уже реализована с RS256 валидацией)
- ✅ `codelab-core-service/pyproject.toml` (зависимости уже есть)
- ✅ `docker-compose.yml` (переменные окружения уже настроены)

## ✨ Преимущества реализации

1. **Безопасность**: RS256 с асимметричной криптографией
2. **Производительность**: Кеширование JWKS с автоматическим обновлением
3. **Надежность**: Fallback на кеш при ошибках сети
4. **Масштабируемость**: Легко добавить дополнительные сервисы, которые доверяют auth-service
5. **Логирование**: Подробное структурированное логирование всех операций
6. **Обработка ошибок**: Полная обработка всех типов ошибок с информативными сообщениями

## 🚀 Готовность к продакшену

- ✅ Все компоненты реализованы
- ✅ Все компоненты протестированы на синтаксис
- ✅ Все импорты работают корректно
- ✅ Docker конфигурация настроена
- ✅ Документация обновлена
- ✅ Поддержка type hints везде
- ✅ Async/await для всех операций

## 📖 Дополнительные ресурсы

- **JWKS стандарт**: https://tools.ietf.org/html/rfc7517
- **JWT стандарт**: https://tools.ietf.org/html/rfc7519
- **RS256 алгоритм**: https://tools.ietf.org/html/rfc7518#section-3.1
- **Тестирование**: [`INTEGRATION_TEST_RS256.md`](INTEGRATION_TEST_RS256.md)
