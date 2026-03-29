# JWT Validation Specification

**Версия:** 1.0.0  
**Статус:** ✅ Production Ready  
**Дата обновления:** 29 марта 2026

---

## 📋 Обзор

Core Service валидирует JWT токены, полученные от auth-service, используя асимметричную криптографию RS256. Это позволяет безопасно проверять аутентичность и целостность токенов без необходимости синхронизации шифровальных ключей между сервисами.

**Назначение:** Извлечение и валидация информации о пользователе из JWT токенов для обеспечения аутентификации и авторизации.

---

## 🔍 Процесс валидации JWT

### Этапы валидации

```
1. Получить JWT из Authorization header
   ↓
2. Декодировать header JWT (без проверки подписи)
   ↓
3. Извлечь Key ID (kid) из заголовка
   ↓
4. Получить публичный ключ через JWKS клиент
   ↓
5. Валидировать подпись JWT используя публичный ключ
   ↓
6. Валидировать claims:
   - Истечение (exp)
   - Издатель (iss)
   - Аудитория (aud)
   - Тип токена (type)
   ↓
7. Извлечь user_id из claim "sub" (UUID)
   ↓
8. Успешная валидация ✅
```

---

## 🛠️ JWKS Клиент

### Назначение

[`JWKSClient`](../../../app/services/jwks_client.py:16) — асинхронный клиент для:
- Получения JWKS (JSON Web Key Set) от auth-service
- Кеширования ключей для оптимизации производительности
- Получения публичного ключа по Key ID (kid)
- Валидации JWT токенов с RS256

### Инициализация

```python
from app.services.jwks_client import JWKSClient
from app.config import settings

# Создать экземпляр JWKS клиента
client = JWKSClient(
    jwks_url=settings.auth_service_jwks_url,
    cache_ttl=settings.jwks_cache_ttl,  # TTL в секундах
    timeout=10  # Timeout для HTTP запросов
)
```

**Параметры:**

| Параметр | Тип | Описание | По умолчанию |
|----------|-----|---------|--------------|
| `jwks_url` | str | URL JWKS endpoint auth-service | `http://codelab-auth-service:8003/.well-known/jwks.json` |
| `cache_ttl` | int | TTL кеша в секундах | `3600` (1 час) |
| `timeout` | int | Timeout HTTP запроса в секундах | `10` |

### Кеширование JWKS

#### Стратегия кеширования

```
Время (сек)         Статус
───────────────────────────────────────
0 сек    ├─ JWKS загружен в кеш
         │  `_cache_timestamp = 0`
         │  `_jwks_cache = {...}`
         │
1800 сек ├─ Половина TTL
         │  Кеш ещё валиден (осталось 1800 сек)
         │
3600 сек ├─ TTL истёк (3600 сек)
         │  `_is_cache_expired() = True`
         │  ← Запустить refresh кеша
         │
3605 сек ├─ Новый JWKS загружен
         │  `_cache_timestamp = 3605`
         │  `_jwks_cache = {...}` (обновлено)
```

#### Код кеширования

```python
class JWKSClient:
    def __init__(self, ...):
        self._jwks_cache: Optional[dict] = None
        self._cache_timestamp: float = 0
        self.cache_ttl: int = 3600  # 1 час
    
    def _is_cache_expired(self) -> bool:
        """Проверить, истек ли кеш"""
        if not self._jwks_cache:
            return True
        
        elapsed = time.time() - self._cache_timestamp
        return elapsed > self.cache_ttl
    
    async def get_jwks(self) -> dict[str, Any]:
        """Получить JWKS с автоматическим обновлением кеша"""
        if self._is_cache_expired():
            await self._refresh_cache()
        
        return self._jwks_cache
```

#### Fallback при ошибках сети

Если auth-service недоступен:

```python
async def _fetch_jwks(self) -> dict:
    """Получить JWKS от auth-service"""
    try:
        client = await self._get_http_client()
        response = await client.get(self.jwks_url)
        response.raise_for_status()
        
        jwks = response.json()
        logger.info("JWKS fetched successfully", keys_count=len(jwks["keys"]))
        return jwks
        
    except httpx.HTTPError as e:
        logger.error("HTTP error fetching JWKS", error=str(e))
        
        # Fallback: использовать кешированный JWKS
        if self._jwks_cache:
            logger.warning("JWKS fetch failed, using cached version")
            return self._jwks_cache
        
        # Нет кеша → ошибка
        raise JWTError(f"Failed to fetch JWKS: {str(e)}")
```

**Преимущества:**
- ✅ Если auth-service временно недоступен, используется кешированный JWKS
- ✅ Не прерывает обработку запросов пользователей
- ✅ Логирует предупреждение о проблеме с сетью

### Методы JWKSClient

#### `async get_jwks() -> dict[str, Any]`

Получить полный JWKS от auth-service с кешированием.

```python
async with JWKSClient() as client:
    jwks = await client.get_jwks()
    # jwks = {
    #   "keys": [
    #     {
    #       "kty": "RSA",
    #       "kid": "2024-01-key-1",
    #       "n": "...",
    #       "e": "AQAB"
    #     }
    #   ]
    # }
```

**Возвращает:** JWKS словарь с публичными ключами

**Исключения:**
- `JWTError` — Ошибка при получении или парсинге JWKS

#### `async get_public_key(kid: str) -> str`

Получить публичный ключ в PEM формате по Key ID.

```python
async with JWKSClient() as client:
    public_key_pem = await client.get_public_key("2024-01-key-1")
    # -----BEGIN PUBLIC KEY-----
    # MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
    # -----END PUBLIC KEY-----
```

**Параметры:**
- `kid` — Key ID для поиска в JWKS

**Возвращает:** Публичный ключ в PEM формате (строка)

**Исключения:**
- `JWTError` — Ключ с таким kid не найден в JWKS

#### `async validate_token(token: str, issuer: str | None = None, audience: str | None = None) -> dict[str, Any]`

Валидировать JWT токен и вернуть payload.

```python
async with JWKSClient() as client:
    try:
        payload = await client.validate_token(
            token="eyJhbGciOiJSUzI1NiIs...",
            issuer="https://auth.codelab.local",
            audience="codelab-api"
        )
        # payload = {
        #   "iss": "https://auth.codelab.local",
        #   "sub": "550e8400-e29b-41d4-a716-446655440000",
        #   "aud": "codelab-api",
        #   "exp": 1710000900,
        #   "iat": 1710000000,
        #   ...
        # }
    except JWTError as e:
        logger.error(f"Token validation failed: {e}")
```

**Параметры:**
- `token` — JWT токен для валидации
- `issuer` — Ожидаемый издатель (опционально, для валидации)
- `audience` — Ожидаемая аудитория (опционально, для валидации)

**Возвращает:** Распарсенный payload (словарь с claims)

**Исключения:**
- `JWTError` — Ошибки валидации (неверная подпись, истёк токен, неверный issuer/audience)

---

## 🎯 Обработка ошибок валидации

### Типы ошибок валидации

| Ошибка | Описание | HTTP Статус | Действие |
|--------|---------|------------|---------|
| Missing token | Нет Authorization header | 401 Unauthorized | Запросить логин |
| Invalid format | Неверный формат JWT | 401 Unauthorized | Запросить новый токен |
| Invalid signature | Подпись не прошла проверку | 401 Unauthorized | Токен поддельный, отклонить |
| Token expired | Время истечения прошло | 401 Unauthorized | Использовать refresh token |
| Invalid issuer | iss claim не совпадает | 401 Unauthorized | Токен из неправильного источника |
| Invalid audience | aud claim не совпадает | 401 Unauthorized | Токен не для этого сервиса |
| Key not found | kid не найден в JWKS | 401 Unauthorized | Ключ был удалён, нужен новый токен |
| JWKS unavailable | Не удалось получить JWKS | 503 Service Unavailable | Повторить позже |

### Пример обработки ошибок

```python
from jose import JWTError, jwt

async def validate_request_token(token: str) -> dict:
    """Валидировать токен в запросе"""
    try:
        # Извлечь kid из заголовка (без проверки подписи)
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        
        if not kid:
            raise JWTError("Missing 'kid' in token header")
        
        # Получить публичный ключ через JWKS клиент
        jwks_client = get_jwks_client()
        public_key = await jwks_client.get_public_key(kid)
        
        # Валидировать токен
        payload = await jwks_client.validate_token(
            token,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience
        )
        
        return payload
        
    except JWTError as e:
        # Логировать ошибку
        logger.warning(
            "token_validation_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        
        # Возвращать 401 Unauthorized
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
    
    except Exception as e:
        # Неожиданная ошибка
        logger.error(
            "unexpected_error_during_validation",
            error=str(e),
            error_type=type(e).__name__
        )
        
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
```

---

## 📊 Примеры валидации

### Пример 1: Успешная валидация

```python
# Получен валидный access token
token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjIwMjQtMDEta2V5LTEifQ.eyJpc3MiOiJodHRwczovL2F1dGguY29kZWxhYi5sb2NhbCIsInN1YiI6IjU1MGU4NDAwLWUyOWItNDFkNC1hNzE2LTQ0NjY1NTQ0MDAwMCIsImF1ZCI6ImNvZGVsYWItYXBpIiwiZXhwIjoxNzEwMDAwOTAwLCJpYXQiOjE3MTAwMDAwMDAsInR5cGUiOiJhY2Nlc3MifQ..."

jwks_client = JWKSClient()

# Шаг 1: Декодировать header
header = jwt.get_unverified_header(token)
# header = {
#   "alg": "RS256",
#   "typ": "JWT",
#   "kid": "2024-01-key-1"
# }

# Шаг 2: Получить публичный ключ
public_key = await jwks_client.get_public_key(header["kid"])

# Шаг 3: Валидировать токен
payload = jwt.decode(
    token,
    public_key,
    algorithms=["RS256"],
    audience="codelab-api",
    issuer="https://auth.codelab.local",
    options={"verify_exp": True}
)

# payload = {
#   "iss": "https://auth.codelab.local",
#   "sub": "550e8400-e29b-41d4-a716-446655440000",  ← User ID
#   "aud": "codelab-api",
#   "exp": 1710000900,
#   "iat": 1710000000,
#   "type": "access"
# }

user_id = payload["sub"]  # "550e8400-e29b-41d4-a716-446655440000"
```

### Пример 2: Истекший токен

```python
# Токен создан в 10:00:00, истекает в 10:15:00
# Текущее время: 10:16:00 (на 1 минуту позже exp)

token = "eyJhbGciOiJSUzI1NiIs...exp: 1710000900..."

try:
    payload = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        options={"verify_exp": True}
    )
except JWTError as e:
    # JWTClaimsError: Token is expired
    logger.warning(f"Token expired: {e}")
    
    # Клиент должен получить новый access token используя refresh token
```

### Пример 3: Неверная подпись

```python
# Токен подделан: payload изменён, но подпись не обновлена

token_header = "eyJhbGciOiJSUzI1NiIs..."
token_payload = "eyJzdWIiOiJmYWtlLXVzZXItaWQifQ..."  # ← Измененный payload
token_signature = "SIGNATURE_FROM_ORIGINAL_TOKEN"

forged_token = f"{token_header}.{token_payload}.{token_signature}"

try:
    payload = jwt.decode(
        forged_token,
        public_key,
        algorithms=["RS256"]
    )
except JWTError as e:
    # JWTSignatureError: Signature verification failed
    logger.error(f"Invalid signature: {e}")
    # Отклонить запрос
```

---

## 🔐 Безопасность валидации

### Защита от атак

| Атака | Защита | Как работает |
|-------|--------|-------------|
| **Подделка токена** | Проверка подписи RS256 | Подпись может быть создана только приватным ключом (в auth-service) |
| **Модификация payload** | Валидация подписи | Любое изменение payload сделает подпись невалидной |
| **Истёкший токен** | Проверка `exp` claim | Валидация exp перед использованием |
| **Token replay** | Проверка `iat` и TTL | Старые токены со временем истекают |
| **Неправильный издатель** | Проверка `iss` claim | Принимаем только токены от auth-service |
| **Использование для другого сервиса** | Проверка `aud` claim | Принимаем только токены для `codelab-api` |
| **Использование refresh токена как access** | Проверка `type` claim | Разные типы токенов имеют разные назначения |

### Требования валидации

```python
# Обязательные проверки
validation_options = {
    "verify_signature": True,      # ✅ Проверить подпись (обязательно)
    "verify_exp": True,            # ✅ Проверить истечение
    "verify_aud": True,            # ✅ Проверить аудиторию
    "verify_iss": True,            # ✅ Проверить издателя
    "verify_iat": True,            # ✅ Проверить время создания
}

# Дополнительные проверки (вручную)
# - Тип токена (type = "access" или "refresh")
# - Наличие `sub` claim (User ID)
# - Формат `sub` (должен быть UUID)
```

---

## 🔗 Глобальный JWKS Клиент

### Получение глобального экземпляра

```python
from app.services.jwks_client import get_jwks_client, close_jwks_client

# Получить глобальный экземпляр при запуске приложения
async def startup():
    jwks_client = get_jwks_client()
    logger.info("JWKS client initialized")

# Закрыть при остановке приложения
async def shutdown():
    await close_jwks_client()
    logger.info("JWKS client closed")

# В FastAPI
app.add_event_handler("startup", startup)
app.add_event_handler("shutdown", shutdown)
```

### Использование в middleware

```python
from app.services.jwks_client import get_jwks_client

async def auth_middleware(request: Request, call_next):
    """Middleware для валидации JWT токена"""
    token = extract_token_from_header(request)
    
    if not token:
        return JSONResponse({"error": "Missing token"}, status_code=401)
    
    try:
        jwks_client = get_jwks_client()
        payload = await jwks_client.validate_token(
            token,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience
        )
        
        # Сохранить user_id в request для использования в handlers
        request.state.user_id = payload["sub"]
        
    except JWTError:
        return JSONResponse({"error": "Invalid token"}, status_code=401)
    
    return await call_next(request)
```

---

## 📝 Конфигурация

```python
# app/config.py

# JWT RS256 Configuration
JWT_ISSUER: str = "https://auth.codelab.local"
JWT_AUDIENCE: str = "codelab-api"
AUTH_SERVICE_JWKS_URL: str = "http://codelab-auth-service:8003/.well-known/jwks.json"
JWKS_CACHE_TTL: int = 3600  # 1 час
```

Переменные окружения:

```bash
# .env
JWT_ISSUER=https://auth.codelab.local
JWT_AUDIENCE=codelab-api
AUTH_SERVICE_JWKS_URL=http://codelab-auth-service:8003/.well-known/jwks.json
JWKS_CACHE_TTL=3600
```

---

## 📚 Ссылки

- [RFC 7519 — JSON Web Token (JWT)](https://tools.ietf.org/html/rfc7519)
- [RFC 7517 — JSON Web Key (JWK)](https://tools.ietf.org/html/rfc7517)
- [PyJWT Documentation](https://pyjwt.readthedocs.io/)
- [python-jose Documentation](https://python-jose.readthedocs.io/)

---

## 🔗 Связанная документация

- Auth Service: [`jwt-rs256-integration.md`](../../codelab-auth-service/openspec/specs/jwt-rs256-integration.md)
- Core Service: [`authentication-middleware/spec.md`](../authentication-middleware/spec.md)
- Core Service: [`integration-with-auth-service/spec.md`](../integration-with-auth-service/spec.md)
