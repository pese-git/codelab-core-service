# JWT RS256 Integration Test Guide

## 🧪 Тестирование интеграции auth-service и core-service

### Предусловия
- auth-service запущен на `http://codelab-auth-service:8003`
- core-service запущен на `http://localhost:8000`
- Оба сервиса в одной Docker сети

### 1. Проверка JWKS endpoint

```bash
# Получить публичные ключи от auth-service
curl -X GET http://codelab-auth-service:8003/.well-known/jwks.json | jq .

# Ожидаемый ответ:
# {
#   "keys": [
#     {
#       "kty": "RSA",
#       "kid": "key-id-1",
#       "use": "sig",
#       "alg": "RS256",
#       "n": "...",
#       "e": "AQAB"
#     }
#   ]
# }
```

### 2. Получение JWT токена от auth-service

```bash
# Логин пользователя и получение токена
curl -X POST http://codelab-auth-service:8003/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }' | jq .

# Сохранить токен из ответа:
# export JWT_TOKEN="eyJhbGciOiJSUzI1NiIsImtpZCI6ImtleS1pZC0xIn0..."
```

### 3. Проверка структуры JWT токена

```bash
# Декодировать токен (без верификации подписи)
# Используйте https://jwt.io или:

python3 << 'EOF'
import jwt
import json
import base64

token = "YOUR_JWT_TOKEN_HERE"

# Получить части токена
parts = token.split('.')
header = json.loads(base64.urlsafe_b64decode(parts[0] + '=='))
payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))

print("Header:")
print(json.dumps(header, indent=2))
print("\nPayload:")
print(json.dumps(payload, indent=2))
EOF
```

**Ожидаемые поля в payload:**
```json
{
  "sub": "uuid-of-user",
  "type": "access",
  "issuer": "https://auth.codelab.local",
  "audience": "codelab-api",
  "exp": 1234567890,
  "iat": 1234567800
}
```

### 4. Проверка валидации токена в core-service

```bash
# Отправить токен в защищённый endpoint core-service
curl -X GET http://localhost:8000/my/projects \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json"

# Ожидаемые ответы:
# - 200: Успешно, пользователь аутентифицирован
# - 401: Invalid or expired token
# - 401: Missing or invalid Authorization header
```

### 5. Проверка логов middleware

```bash
# Логи успешной валидации:
# {
#   "event": "user_authenticated",
#   "user_id": "uuid-of-user",
#   "path": "/my/projects",
#   "method": "GET"
# }

# Логи ошибок валидации:
# {
#   "event": "invalid_jwt_token",
#   "error": "Invalid signature",
#   "path": "/my/projects"
# }
```

### 6. Проверка кеширования JWKS

```bash
# Проверить логи после первого запроса (должен загрузить JWKS):
# {
#   "event": "jwks_fetched_successfully",
#   "keys_count": 1
# }

# Проверить последующие запросы (должны использовать кеш):
# {
#   "event": "jwks_cache_updated",
#   "cache_ttl": 3600
# }

# После истечения TTL (3600 сек = 1 час) JWKS должен обновиться автоматически
```

### 7. Проверка обработки ошибок

**Тест 1: Истекший токен**
```bash
curl -X GET http://localhost:8000/my/projects \
  -H "Authorization: Bearer expired_token" \
  -H "Content-Type: application/json"
# Ожидается: 401 UNAUTHORIZED
```

**Тест 2: Неверная подпись**
```bash
# Закодировать токен с неверной подписью
curl -X GET http://localhost:8000/my/projects \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0In0.invalid_signature" \
  -H "Content-Type: application/json"
# Ожидается: 401 UNAUTHORIZED
```

**Тест 3: Отсутствие токена**
```bash
curl -X GET http://localhost:8000/my/projects \
  -H "Content-Type: application/json"
# Ожидается: 401 UNAUTHORIZED - Missing or invalid Authorization header
```

**Тест 4: Неверный формат токена**
```bash
curl -X GET http://localhost:8000/my/projects \
  -H "Authorization: NotBearer token" \
  -H "Content-Type: application/json"
# Ожидается: 401 UNAUTHORIZED
```

### 8. Проверка claim `sub` в UUID формате

```bash
# Проверить логи:
# {
#   "event": "user_authenticated",
#   "user_id": "550e8400-e29b-41d4-a716-446655440000"  # UUID v4 формат
# }

# Если user_id не в UUID формате:
# {
#   "event": "invalid_user_id_format",
#   "error": "invalid UUID in sub claim"
# }
```

### 9. Интеграционный тест (Python)

```python
import asyncio
import httpx
from app.services.jwks_client import JWKSClient

async def test_rs256_integration():
    """Тест интеграции RS256 между auth и core сервисами."""
    
    client = JWKSClient(
        jwks_url="http://codelab-auth-service:8003/.well-known/jwks.json",
        cache_ttl=3600
    )
    
    try:
        # 1. Получить JWKS от auth-service
        jwks = await client.get_jwks()
        print(f"✓ JWKS загружен: {len(jwks.get('keys', []))} ключей")
        
        # 2. Получить токен от auth-service (пример)
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                "http://codelab-auth-service:8003/api/v1/auth/login",
                json={"email": "test@example.com", "password": "password123"}
            )
            if response.status_code == 200:
                token = response.json()["access_token"]
                
                # 3. Валидировать токен используя JWKS клиент
                payload = await client.validate_token(
                    token,
                    issuer="https://auth.codelab.local",
                    audience="codelab-api"
                )
                print(f"✓ Токен валидирован: user_id={payload.get('sub')}")
            else:
                print(f"✗ Ошибка логина: {response.status_code}")
        
        # 4. Проверить кеширование
        jwks_cached = await client.get_jwks()
        print(f"✓ JWKS закеширован: {len(jwks_cached.get('keys', []))} ключей")
        
        await client.close()
        print("\n✓ Все тесты пройдены успешно!")
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        await client.close()

# Запустить тест
if __name__ == "__main__":
    asyncio.run(test_rs256_integration())
```

### 10. Запуск теста через Docker Compose

```bash
# Запустить все сервисы
docker-compose up -d

# Проверить логи core-service
docker-compose logs -f codelab-core-service

# Проверить логи auth-service
docker-compose logs -f codelab-auth-service

# Выполнить тестовый запрос
docker-compose exec codelab-core-service curl -X GET http://localhost:8000/health
```

### ✅ Чек-лист успешной интеграции

- [ ] JWKS endpoint доступен от core-service
- [ ] JWT токены подписаны RS256 в auth-service
- [ ] Core-service успешно загружает JWKS
- [ ] Токены валидируются с правильным `issuer` и `audience`
- [ ] User_id извлекается из claim `sub` в UUID формате
- [ ] Истекшие токены отклоняются
- [ ] Токены с неверной подписью отклоняются
- [ ] JWKS кешируется правильно
- [ ] Middleware логирует все важные события
- [ ] Обработка ошибок сети работает корректно (fallback на кеш)

### 🐛 Отладка проблем

**Проблема: "Unable to find JWKS endpoint"**
```
Решение:
1. Проверить что auth-service запущен: curl http://codelab-auth-service:8003/api/v1/jwks.json
2. Проверить сетевую доступность между контейнерами
3. Проверить конфигурацию AUTH_SERVICE_JWKS_URL в core-service
```

**Проблема: "Unable to find a signing key that matches"**
```
Решение:
1. Проверить что kid в токене совпадает с kid в JWKS
2. Проверить что JWKS обновлен на auth-service
3. Проверить логи auth-service для проблем с генерацией ключей
```

**Проблема: "Invalid signature"**
```
Решение:
1. Убедиться что auth-service подписывает токены RS256
2. Проверить что публичный ключ совпадает с приватным на auth-service
3. Проверить что токен не был изменен в транзите
```

**Проблема: "Invalid issuer" или "Invalid audience"**
```
Решение:
1. Проверить конфигурацию JWT_ISSUER в core-service
2. Проверить конфигурацию JWT_AUDIENCE в core-service
3. Убедиться что auth-service указывает правильные issuer/audience в токене
```
