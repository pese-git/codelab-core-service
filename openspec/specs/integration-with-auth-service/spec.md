# Integration with Auth Service - JWT RS256 Specification

**Версия:** 1.0.0  
**Статус:** ✅ Production Ready  
**Дата обновления:** 29 марта 2026

---

## 📋 Обзор интеграции

Core Service интегрируется с Auth Service для валидации JWT токенов. Интеграция построена на асимметричной криптографии RS256 (RSA + SHA-256), что позволяет валидировать токены без обмена секретными ключами между сервисами.

**Архитектура:**

```
┌──────────────────────────────────────────────────────────────┐
│                      Client (Frontend)                        │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            │ 1. POST /oauth/token
                            │    (username, password)
                            ▼
        ┌───────────────────────────────────────┐
        │      Auth Service (8003)              │
        │  ┌─────────────────────────────────┐  │
        │  │ TokenService: Создаёт JWT      │  │
        │  │ (подписывает приватным ключом) │  │
        │  └─────────────────────────────────┘  │
        │                                       │
        │  ┌─────────────────────────────────┐  │
        │  │ JWKS Service: Публикует JWKS    │  │
        │  │ (публичные ключи)               │  │
        │  │ GET /.well-known/jwks.json      │  │
        │  └─────────────────────────────────┘  │
        └───────────────────────────────────────┘
                            │
                            │ 2. access_token
                            │    refresh_token
                            ▼
        ┌───────────────────────────────────────┐
        │    Client with JWT                    │
        │    Authorization: Bearer <token>      │
        └───────────────┬───────────────────────┘
                        │
                        │ 3. API Request with JWT
                        ▼
        ┌───────────────────────────────────────┐
        │      Core Service (8000)              │
        │  ┌─────────────────────────────────┐  │
        │  │ AuthenticationMiddleware        │  │
        │  │ 1. Извлечь JWT из header       │  │
        │  │ 2. Получить kid из токена      │  │
        │  │ 3. Запросить JWKS у auth-svc   │  │
        │  │ 4. Получить публичный ключ    │  │
        │  │ 5. Валидировать подпись       │  │
        │  │ 6. Проверить claims            │  │
        │  │ 7. Инъекция user_id            │  │
        │  └─────────────────────────────────┘  │
        │                                       │
        │  ┌─────────────────────────────────┐  │
        │  │ JWKSClient                      │  │
        │  │ - Асинхронные запросы           │  │
        │  │ - Кэширование с TTL 1 час      │  │
        │  │ - Fallback при ошибках         │  │
        │  └─────────────────────────────────┘  │
        └───────────────────────────────────────┘
                        │
                        │ 4. Response
                        ▼
        ┌───────────────────────────────────────┐
        │    Client: 200 OK с данными           │
        └───────────────────────────────────────┘
```

---

## 🌐 Конфигурация сервисов

### Auth Service (Издатель токенов)

**Сервис:** codelab-auth-service  
**Порт:** 8003  
**Назначение:** Генерирует и подписывает JWT токены

**Переменные окружения:**

```bash
# .env (auth-service)

# JWT Configuration
CORE_SERVICE_JWT_ISSUER=https://auth.codelab.local
CORE_SERVICE_JWT_AUDIENCE=codelab-api
ACCESS_TOKEN_LIFETIME=900       # 15 минут
REFRESH_TOKEN_LIFETIME=2592000  # 30 дней

# RSA Key Management
RSA_PRIVATE_KEY_PATH=keys/private_key.pem
RSA_PRIVATE_KEY_BACKUP_PATH=keys/private_key.backup.pem

# Key Rotation
CURRENT_KEY_ID=2024-01-key-1
```

**Ключевые компоненты:**

| Компонент | Файл | Назначение |
|-----------|------|-----------|
| TokenService | `app/services/token_service.py` | Создание JWT токенов |
| JWKSService | `app/services/jwks_service.py` | Формирование JWKS response |
| RSAKeyManager | `app/core/security.py` | Управление RSA ключами |
| JWKS Endpoint | `app/api/v1/jwks.py` | GET /.well-known/jwks.json |

### Core Service (Потребитель токенов)

**Сервис:** codelab-core-service  
**Порт:** 8000  
**Назначение:** Валидирует JWT токены для доступа к ресурсам

**Переменные окружения:**

```bash
# .env (core-service)

# JWT RS256 Configuration
CORE_SERVICE_JWT_ISSUER=https://auth.codelab.local
CORE_SERVICE_JWT_AUDIENCE=codelab-api
CORE_SERVICE_AUTH_SERVICE_JWKS_URL=http://codelab-auth-service:8003/.well-known/jwks.json
CORE_SERVICE_JWKS_CACHE_TTL=3600  # 1 час

# Optional: для локальной разработки
AUTH_SERVICE_JWKS_URL_DEV=http://localhost:8003/.well-known/jwks.json
```

**Ключевые компоненты:**

| Компонент | Файл | Назначение |
|-----------|------|-----------|
| JWKSClient | `app/services/jwks_client.py` | Получение и кэширование JWKS |
| AuthenticationMiddleware | `app/middleware/user_isolation.py` | Валидация JWT в запросах |
| JWT Validation | `app/dependencies.py` | Зависимости для валидации |

---

## 🔄 Поток аутентификации

### Сценарий 1: Успешная аутентификация и доступ

```mermaid
sequenceDiagram
    participant Client
    participant AuthService as Auth Service<br/>(8003)
    participant CoreService as Core Service<br/>(8000)

    Client->>AuthService: POST /oauth/token<br/>(username, password)
    AuthService->>AuthService: 1. Валидировать credentials
    AuthService->>AuthService: 2. Создать JWT payload
    AuthService->>AuthService: 3. Подписать приватным ключом
    AuthService-->>Client: 200 OK<br/>{access_token, refresh_token}

    Client->>CoreService: GET /my/projects<br/>Authorization: Bearer <access_token>
    CoreService->>CoreService: 1. Извлечь токен
    CoreService->>CoreService: 2. Получить kid из заголовка
    CoreService->>AuthService: 3. GET /.well-known/jwks.json
    AuthService-->>CoreService: JWKS {keys: [...]}
    CoreService->>CoreService: 4. Кэшировать JWKS
    CoreService->>CoreService: 5. Получить публичный ключ по kid
    CoreService->>CoreService: 6. Валидировать подпись
    CoreService->>CoreService: 7. Проверить claims (iss, aud, exp)
    CoreService->>CoreService: 8. Инъекция user_id в request
    CoreService->>CoreService: 9. Обработать запрос handler'ом
    CoreService-->>Client: 200 OK<br/>{projects: [...]}
```

### Сценарий 2: Истёкший access token

```mermaid
sequenceDiagram
    participant Client
    participant AuthService as Auth Service<br/>(8003)
    participant CoreService as Core Service<br/>(8000)

    Client->>CoreService: GET /my/projects<br/>Authorization: Bearer <expired_token>
    CoreService->>CoreService: 1. Получить kid
    CoreService->>CoreService: 2. Валидировать подпись (OK)
    CoreService->>CoreService: 3. Проверить exp (EXPIRED)
    CoreService-->>Client: 401 Unauthorized<br/>{error: "Token expired"}

    Client->>AuthService: POST /oauth/token<br/>grant_type=refresh_token<br/>refresh_token=<token>
    AuthService->>AuthService: 1. Валидировать refresh token
    AuthService->>AuthService: 2. Создать новый access token
    AuthService-->>Client: 200 OK<br/>{access_token: <новый>}

    Client->>CoreService: GET /my/projects<br/>Authorization: Bearer <новый_token>
    CoreService->>CoreService: Валидировать новый token (OK)
    CoreService-->>Client: 200 OK<br/>{projects: [...]}
```

### Сценарий 3: Ротация ключей

```mermaid
sequenceDiagram
    participant Client
    participant AuthService as Auth Service<br/>(8003)
    participant CoreService as Core Service<br/>(8000)

    AuthService->>AuthService: 1. Создать новый RSA ключ
    AuthService->>AuthService: 2. Новый kid = "2024-02-key-2"
    AuthService->>AuthService: 3. Оба ключа в JWKS

    Client->>AuthService: POST /oauth/token
    AuthService->>AuthService: Подписать НОВЫМ ключом (2024-02-key-2)
    AuthService-->>Client: {access_token: <signed_with_2024-02-key-2>}

    Client->>CoreService: GET /my/projects<br/>Authorization: Bearer <token>
    CoreService->>CoreService: 1. Получить kid = "2024-02-key-2"
    CoreService->>CoreService: 2. Проверить локальный кэш JWKS
    CoreService->>CoreService: Кэш истёк или нет ключа
    CoreService->>AuthService: 3. GET /.well-known/jwks.json
    AuthService-->>CoreService: JWKS с обоими ключами
    CoreService->>CoreService: 4. Кэшировать новый JWKS
    CoreService->>CoreService: 5. Получить публичный ключ (2024-02-key-2)
    CoreService->>CoreService: 6. Валидировать подпись (OK)
    CoreService-->>Client: 200 OK
```

---

## 📤 Request/Response примеры

### Пример 1: Получение токенов

**Request:**

```http
POST /oauth/token HTTP/1.1
Host: codelab-auth-service:8003
Content-Type: application/x-www-form-urlencoded

grant_type=password&
username=john@example.com&
password=MyPassword123!&
client_id=codelab-flutter-app&
scope=api:read+api:write
```

**Response (200 OK):**

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjIwMjQtMDEta2V5LTEifQ.eyJpc3MiOiJodHRwczovL2F1dGguY29kZWxhYi5sb2NhbCIsInN1YiI6IjU1MGU4NDAwLWUyOWItNDFkNC1hNzE2LTQ0NjY1NTQ0MDAwMCIsImF1ZCI6ImNvZGVsYWItYXBpIiwiZXhwIjoxNzEwMDAwOTAwLCJpYXQiOjE3MTAwMDAwMDAsInR5cGUiOiJhY2Nlc3MiLCJjbGllbnRfaWQiOiJjb2RlbGFiLWZsdXR0ZXItYXBwIn0.SIGNATURE...",
  "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjIwMjQtMDEta2V5LTEifQ.eyJpc3MiOiJodHRwczovL2F1dGguY29kZWxhYi5sb2NhbCIsInN1YiI6IjU1MGU4NDAwLWUyOWItNDFkNC1hNzE2LTQ0NjY1NTQ0MDAwMCIsImF1ZCI6ImNvZGVsYWItYXBpIiwiZXhwIjoxNzEyNTkyMDAwLCJpYXQiOjE3MTAwMDAwMDAsInR5cGUiOiJyZWZyZXNoIn0.SIGNATURE...",
  "token_type": "bearer",
  "expires_in": 900,
  "scope": "api:read api:write"
}
```

### Пример 2: Доступ к защищённому ресурсу

**Request:**

```http
GET /my/projects HTTP/1.1
Host: codelab-core-service:8000
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjIwMjQtMDEta2V5LTEifQ.eyJpc3MiOiJodHRwczovL2F1dGguY29kZWxhYi5sb2NhbCIsInN1YiI6IjU1MGU4NDAwLWUyOWItNDFkNC1hNzE2LTQ0NjY1NTQ0MDAwMCIsImF1ZCI6ImNvZGVsYWItYXBpIiwiZXhwIjoxNzEwMDAwOTAwLCJpYXQiOjE3MTAwMDAwMDAsInR5cGUiOiJhY2Nlc3MiLCJjbGllbnRfaWQiOiJjb2RlbGFiLWZsdXR0ZXItYXBwIn0.SIGNATURE...
```

**Response (200 OK):**

```json
{
  "projects": [
    {
      "id": "uuid-1",
      "name": "Project 1",
      "created_at": "2026-03-29T10:00:00Z"
    },
    {
      "id": "uuid-2",
      "name": "Project 2",
      "created_at": "2026-03-29T09:00:00Z"
    }
  ]
}
```

### Пример 3: Получение JWKS

**Request:**

```http
GET /.well-known/jwks.json HTTP/1.1
Host: codelab-auth-service:8003
Accept: application/json
```

**Response (200 OK):**

```json
{
  "keys": [
    {
      "kty": "RSA",
      "use": "sig",
      "kid": "2024-01-key-1",
      "alg": "RS256",
      "n": "xjlCRBKHfh5nvBELlKXXM2S5GZ8w4-JKZH6kN8P5Q6R7S8T9U0V1W2X3Y4Z5A6B7C8D9E0F1G2H3I4J5K6L7M8N9O0P1Q2R3S4T5U6V7W8X9Y0Z1A2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P7Q8R9S0T1U2V3W4X5Y6Z7A8B9C0D1E2F3G4H5I6J7K8L9M0N1O2P3Q4R5S6T7U8V9W0X1Y2Z3A4B5C6D7E8F9G0H1I2J3K4L5M6N7O8P9Q0R1S2T3U4V5W6X7Y8Z9A0B1C2D3E4F5G6H7I8J9K0L1M2N3O4P5Q6R7S8T9U0V1W2X3Y4Z5A6B7C8D9E0F1G2H3I4J5K6L7M8N9O0P1Q2R3S4T5U6V7W8X9Y0Z1A2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P7Q8R9S0T1U2V3W4X5Y6Z7A8B9",
      "e": "AQAB"
    }
  ]
}
```

---

## ⚙️ Конфигурация и переменные окружения

### Docker Compose (dev)

**Файл:** `docker-compose.yml`

```yaml
version: '3.8'

services:
  codelab-auth-service:
    image: codelab-auth-service:latest
    ports:
      - "8003:8003"
    environment:
      - CORE_SERVICE_JWT_ISSUER=https://auth.codelab.local
      - CORE_SERVICE_JWT_AUDIENCE=codelab-api
      - ACCESS_TOKEN_LIFETIME=900
      - REFRESH_TOKEN_LIFETIME=2592000
      - DATABASE_URL=postgresql://user:password@db:5432/codelab_auth
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./keys:/app/keys  # RSA ключи
    depends_on:
      - db
      - redis
    networks:
      - codelab-network

  codelab-core-service:
    image: codelab-core-service:latest
    ports:
      - "8000:8000"
    environment:
      - CORE_SERVICE_JWT_ISSUER=https://auth.codelab.local
      - CORE_SERVICE_JWT_AUDIENCE=codelab-api
      - CORE_SERVICE_AUTH_SERVICE_JWKS_URL=http://codelab-auth-service:8003/.well-known/jwks.json
      - CORE_SERVICE_JWKS_CACHE_TTL=3600
      - CORE_SERVICE_DATABASE_URL=postgresql://user:password@db:5432/codelab_core
      - CORE_SERVICE_REDIS_URL=redis://redis:6379/1
    depends_on:
      - db
      - redis
      - codelab-auth-service
    networks:
      - codelab-network

networks:
  codelab-network:
    driver: bridge
```

### Production конфигурация

```yaml
services:
  codelab-auth-service:
    environment:
      # JWT
      - JWT_ISSUER=https://auth.codelab.io
      - CORE_SERVICE_JWT_AUDIENCE=codelab-api
      - ACCESS_TOKEN_LIFETIME=900
      - REFRESH_TOKEN_LIFETIME=2592000
      
      # Database
      - DATABASE_URL=postgresql://user:pass@db-prod:5432/codelab_auth
      - DATABASE_SSL_MODE=require
      
      # Redis
      - REDIS_URL=rediss://redis-prod:6379/0
      - REDIS_SSL=true
      
      # Logging
      - LOG_LEVEL=INFO
      - SENTRY_DSN=https://...

  codelab-core-service:
    environment:
      # JWT
      - JWT_ISSUER=https://auth.codelab.io
      - CORE_SERVICE_JWT_AUDIENCE=codelab-api
      - AUTH_SERVICE_JWKS_URL=https://auth.codelab.io/.well-known/jwks.json
      - CORE_SERVICE_JWKS_CACHE_TTL=3600
      
      # Database
      - DATABASE_URL=postgresql://user:pass@db-prod:5432/codelab_core
      - DATABASE_SSL_MODE=require
      
      # Redis
      - REDIS_URL=rediss://redis-prod:6379/1
      - REDIS_SSL=true
      
      # Logging
      - LOG_LEVEL=INFO
      - SENTRY_DSN=https://...
```

---

## 🛡️ Безопасность интеграции

### Защита передачи данных

| Компонент | Защита | Реализация |
|-----------|--------|-----------|
| JWT подпись | RS256 | Приватный ключ только в auth-service |
| HTTPS | TLS 1.2+ | В production используется HTTPS |
| CORS | Настройка | Auth-service предоставляет JWKS для всех сервисов |
| Rate Limiting | Token bucket | На JWT endpoints auth-service |
| Token Lifetime | TTL | Access: 15 мин, Refresh: 30 дней |

### Проверки валидации

**Core Service проверяет:**

```python
# Обязательные проверки
checks = {
    "signature": "RS256 подпись должна быть валидна",
    "issuer": f"iss должен быть {settings.jwt_issuer}",
    "audience": f"aud должна быть {settings.jwt_audience}",
    "expiration": "exp должен быть в будущем",
    "token_type": "type должен быть 'access'",
    "sub_exists": "sub (user_id) должен присутствовать",
}
```

### Ротация ключей

Поддержка безопасной ротации ключей:

```
Шаг 1: Auth Service генерирует новый ключ
  kid = "2024-02-key-2"
  
Шаг 2: Оба ключа активны в JWKS
  ├─ "2024-01-key-1" (старый)
  └─ "2024-02-key-2" (новый)
  
Шаг 3: Новые токены подписываются новым ключом
  
Шаг 4: Core Service получает обновлённый JWKS
  (кэш обновляется автоматически)
  
Шаг 5: Старый ключ удаляется из JWKS
  (после истечения всех старых токенов)
```

---

## 📊 Мониторинг интеграции

### Метрики для отслеживания

```python
# Метрики в Core Service

metrics = {
    "jwt_validation_total": "Всего попыток валидации JWT",
    "jwt_validation_success": "Успешных валидаций",
    "jwt_validation_failed": "Ошибок валидации",
    "jwt_validation_expired": "Истёкших токенов",
    "jwt_validation_invalid_signature": "Невалидных подписей",
    
    "jwks_fetch_total": "Всего запросов JWKS",
    "jwks_fetch_success": "Успешных запросов JWKS",
    "jwks_fetch_failed": "Ошибок запросов JWKS",
    "jwks_fetch_from_cache": "Запросов из кэша",
    
    "jwks_cache_hit_rate": "Процент попаданий в кэш",
    "jwks_cache_age": "Возраст кэша в секундах",
}
```

### Логирование

```python
# Примеры логирования в Core Service

logger.info(
    "token_validated_successfully",
    user_id=payload["sub"],
    token_type=payload["type"],
    exp_timestamp=payload["exp"],
)

logger.warning(
    "token_validation_failed",
    error_type="expired",
    user_id=payload.get("sub"),
)

logger.error(
    "jwks_fetch_failed",
    auth_service_url=settings.auth_service_jwks_url,
    error=str(e),
)
```

---

## 🔗 Проверочный список развёртывания

### Перед развёртыванием

- [ ] Auth Service имеет валидный RSA ключ пару (2048 бит)
- [ ] Auth Service генерирует JWKS в формате RFC 7517
- [ ] Core Service имеет правильный URL JWKS endpoint
- [ ] JWT_ISSUER совпадает в обоих сервисах
- [ ] JWT_AUDIENCE совпадает в обоих сервисах
- [ ] JWKS_CACHE_TTL установлен на разумное значение (3600 сек)
- [ ] Firewall позволяет core-service достучаться до auth-service
- [ ] TLS сертификаты установлены (для production)

### После развёртывания

- [ ] `curl http://auth-service:8003/.well-known/jwks.json` возвращает JWKS
- [ ] Core Service может получить JWKS и закэшировать его
- [ ] JWT токены генерируются с правильным `kid`
- [ ] Core Service валидирует токены успешно
- [ ] Истёкшие токены отклоняются с 401
- [ ] Поддельные токены отклоняются с 401
- [ ] Мониторинг и логирование работают

---

## 🚀 Примеры использования (cURL)

### Получить токены

```bash
curl -X POST http://localhost:8003/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "username=john@example.com" \
  -d "password=MyPassword123!" \
  -d "client_id=codelab-flutter-app" \
  -d "scope=api:read api:write"
```

### Получить JWKS

```bash
curl http://localhost:8003/.well-known/jwks.json | jq
```

### Доступ к защищённому ресурсу

```bash
ACCESS_TOKEN="eyJhbGciOiJSUzI1NiIs..."

curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8000/my/projects | jq
```

### Проверить валидность токена (decode без проверки)

```bash
# Распарсить JWT без проверки подписи (для отладки)
python3 << 'EOF'
import jwt
import json

token = "eyJhbGciOiJSUzI1NiIs..."

# Без проверки подписи (только для отладки!)
header = jwt.get_unverified_header(token)
payload = jwt.decode(token, options={"verify_signature": False})

print("Header:")
print(json.dumps(header, indent=2))
print("\nPayload:")
print(json.dumps(payload, indent=2))
EOF
```

---

## 📚 Ссылки на документацию

- Auth Service: [`jwt-rs256-integration.md`](../../codelab-auth-service/openspec/specs/jwt-rs256-integration.md)
- Core Service: [`jwt-validation/spec.md`](../jwt-validation/spec.md)
- Core Service: [`authentication-middleware/spec.md`](../authentication-middleware/spec.md)
- [RFC 7519 — JWT](https://tools.ietf.org/html/rfc7519)
- [RFC 7517 — JWK](https://tools.ietf.org/html/rfc7517)

---

## 🔄 Обновления и ротация ключей

### Процесс ротации ключей

**День 1: Готовка**
- Auth Service генерирует новый RSA ключ
- Новый kid регистрируется: "2024-02-key-2"
- Оба ключа добавляются в JWKS

**День 2-30: Переходный период**
- Новые токены подписываются новым ключом
- Старые токены остаются валидны (kid: "2024-01-key-1")
- Core Service получает оба ключа из JWKS
- Кэш обновляется автоматически

**День 31+: Вывод старого ключа**
- Все старые токены истекли
- Старый ключ удаляется из JWKS
- Клиенты перестают запрашивать старый ключ

### Откат при проблемах

Если возникли проблемы с новым ключом:

```python
# В Auth Service: откат на старый ключ
CURRENT_KEY_ID = "2024-01-key-1"  # Вернуться на старый

# Новые токены подписываются старым ключом
# Старый ключ восстанавливается в JWKS
# Core Service получит обновлённый JWKS
```

---

## 💡 Troubleshooting

### Core Service не может получить JWKS

```
❌ Error: Failed to fetch JWKS from auth-service

Проверить:
1. URL в AUTH_SERVICE_JWKS_URL правильный
2. Auth Service запущен и доступен
3. Firewall не блокирует соединение
4. DNS разрешает имя auth-service
5. HTTPS сертификаты (если используется HTTPS)

$ curl http://codelab-auth-service:8003/.well-known/jwks.json
```

### JWT валидация падает на issuer

```
❌ Error: Token issuer mismatch

Проверить:
1. JWT_ISSUER в auth-service
2. JWT_ISSUER в core-service (должны быть одинаковыми)
3. Стоп, если есть опечатка в URL

# Auth Service
CORE_SERVICE_JWT_ISSUER=https://auth.codelab.local

# Core Service (должно быть ТО ЖЕ)
CORE_SERVICE_JWT_ISSUER=https://auth.codelab.local
```

### JWT валидация падает на audience

```
❌ Error: Token audience mismatch

Проверить:
1. JWT_AUDIENCE в auth-service
2. JWT_AUDIENCE в core-service (должны быть одинаковыми)

# Обе должны быть одинаковыми:
CORE_SERVICE_JWT_AUDIENCE=codelab-api
```

### JWKS кэш не обновляется

```
❌ Problem: Core Service использует старый JWKS

Решение:
1. Проверить JWKS_CACHE_TTL (обычно 3600 сек)
2. Очистить кэш вручную (перезагрузить сервис)
3. Проверить логи Core Service на ошибки

# В логах должно быть:
jwks_cache_updated: TTL = 3600 seconds
```

---

## 🎯 Резюме интеграции

**Auth Service → Core Service:**
```
Приватный ключ         Публичный ключ
    │                       │
    ├─ Подписывает JWT     │
    │     │                 │
    │     └─ JWKS endpoint ─┘
    │                       │
    └─ Кэширует в JWKS     │
                           ▼
                       Core Service
                          │
                          ├─ Получает JWKS
                          ├─ Кэширует (TTL 1ч)
                          ├─ Валидирует подпись
                          ├─ Проверяет claims
                          └─ Инъекция user context
```

Интеграция безопасна, масштабируема и не требует обмена секретных ключей между сервисами.
