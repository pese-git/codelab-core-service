# Руководство по развёртыванию Production среды

## Обзор

Это руководство описывает процесс развёртывания CodeLab Core Service в production окружении с высокой доступностью, безопасностью и надёжностью.

## Содержание

1. [Требования перед развёртыванием](#требования-перед-развёртыванием)
2. [Усиление безопасности](#усиление-безопасности)
3. [Шаги развёртывания](#шаги-развёртывания)
4. [Проверка после развёртывания](#проверка-после-развёртывания)
5. [Мониторинг и оповещения](#мониторинг-и-оповещения)
6. [Резервные копии и восстановление](#резервные-копии-и-восстановление)
7. [Масштабирование](#масштабирование)
8. [Устранение неисправностей](#устранение-неисправностей)

---

## Требования перед развёртыванием

### Системные требования

- **ОС**: Ubuntu 20.04+ или эквивалентный Linux
- **CPU**: Минимум 4 ядра (рекомендуется 8+ для production)
- **RAM**: Минимум 16GB (рекомендуется 32GB+)
- **Диск**: Минимум 100GB SSD
- **Сеть**: Стабильное интернет-соединение, рекомендуется статический IP

### Требования ПО

```bash
# Проверить версии
docker --version          # Docker 20.10+
docker-compose --version  # Docker Compose 2.0+
bash --version           # GNU Bash 4.0+

# Установить если нужно (Ubuntu/Debian)
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh
sudo usermod -aG docker $USER
```

### Конфигурация firewall

```bash
# Открыть необходимые порты
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 3001/tcp  # Langfuse UI
sudo ufw allow 3000/tcp  # Grafana

# Включить firewall
sudo ufw enable
```

---

## Усиление безопасности

### 1. Конфигурация окружения

```bash
# Генерировать безопасные пароли (минимум 32 символа)
openssl rand -base64 32  # Для всех паролей

# Генерировать ключ шифрования (64 hex символа)
openssl rand -hex 32     # Для ENCRYPTION_KEY

# Копировать и настроить окружение
cp .env.production.example .env.production
nano .env.production

# Установить ограничивающие права доступа
chmod 600 .env.production
```

### 2. Управление секретами

**Рекомендуемый подход**: Использовать менеджер секретов вместо .env файлов:

```bash
# Вариант 1: HashiCorp Vault
docker run -d --name vault \
  -p 8200:8200 \
  -e VAULT_DEV_ROOT_TOKEN_ID=myroot \
  vault

# Вариант 2: AWS Secrets Manager / Google Secret Manager
# Настройте в console вашего облачного провайдера

# Вариант 3: Docker Secrets (для Swarm)
docker secret create db_password <(echo 'your-secure-password')
```

### 3. Безопасность сети

```bash
# Создать изолированную сеть
docker network create codelab-network

# Использовать сетевую область (не открывать внешне)
# Скрыть в docker-compose.prod.yml:
# - Redis (приватный)
# - ClickHouse (приватный)
# - Postgres (приватный)

# Открыть только:
# - Langfuse UI (3001) - через reverse proxy
# - Core App (8000) - через reverse proxy
# - Мониторинг (3000, 9090) - ограниченный доступ
```

### 4. SSL/TLS конфигурация

```bash
# Установить Nginx для reverse proxy + SSL
sudo apt-get install nginx certbot python3-certbot-nginx

# Получить SSL сертификат
sudo certbot certonly --standalone -d your-domain.com

# Создать конфигурацию Nginx
sudo nano /etc/nginx/sites-available/codelab

# Конфигурация Nginx с SSL
upstream langfuse {
    server localhost:3001;
}

upstream app {
    server localhost:8000;
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    location / {
        proxy_pass http://langfuse;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Включить и перезагрузить
sudo ln -s /etc/nginx/sites-available/codelab /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## Шаги развёртывания

### Шаг 1: Подготовка сервера

```bash
# Обновить систему
sudo apt-get update && sudo apt-get upgrade -y

# Создать директорию приложения
sudo mkdir -p /opt/codelab
cd /opt/codelab

# Клонировать репозиторий
git clone https://github.com/your-org/codelab-core-service.git .
```

### Шаг 2: Конфигурация окружения

```bash
# Копировать и редактировать конфигурацию
cp .env.production.example .env.production
nano .env.production

# Убедиться в корректности конфигурации
bash scripts/check-health.sh docker-compose.prod.yml || true
```

### Шаг 3: Инициализация Production окружения

```bash
# Сделать скрипты исполняемыми
chmod +x scripts/*.sh

# Запустить инициализацию
bash scripts/init-production.sh

# Это выполнит:
# - Валидацию конфигурации
# - Проверку Docker установки
# - Остановку существующих контейнеров
# - Сборку image'ей
# - Запуск сервисов
# - Проверку здоровья
```

### Шаг 4: Проверка развёртывания

```bash
# Проверить все сервисы
docker-compose -f docker-compose.prod.yml ps

# Посмотреть логи
docker-compose -f docker-compose.prod.yml logs -f

# Протестировать подключение
curl http://localhost:8000/health
curl http://localhost:3001
```

---

## Проверка после развёртывания

### Проверка здоровья сервисов

```bash
# Запустить полную проверку
bash scripts/check-health.sh docker-compose.prod.yml

# Ожидаемый результат: All services are healthy!
```

### Проверка БД

```bash
# Проверить PostgreSQL
docker-compose -f docker-compose.prod.yml exec postgres \
  psql -U postgres -d codelab -c "\dt"

# Проверить ClickHouse
docker-compose -f docker-compose.prod.yml exec clickhouse \
  clickhouse-client -u clickhouse --password changeme \
  "SHOW DATABASES"
```

### Доступ к приложениям

```
- Langfuse: https://your-domain.com
- Grafana: https://your-domain.com:3000
- Jaeger: https://your-domain.com:16686
- Prometheus: https://your-domain.com:9090
- Core API: https://your-domain.com/api
```

---

## Мониторинг и оповещения

### Конфигурация Prometheus оповещений

Отредактировать `monitoring/prometheus.yml`:

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

rule_files:
  - "/etc/prometheus/alert-rules.yml"
```

### Правила оповещений

```yaml
groups:
  - name: codelab-alerts
    rules:
      - alert: ServiceDown
        expr: up{job="codelab"} == 0
        for: 5m
        annotations:
          summary: "Сервис {{ $labels.instance }} недоступен"
      
      - alert: HighMemoryUsage
        expr: (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) < 0.1
        for: 10m
        annotations:
          summary: "Высокое потребление памяти на {{ $labels.instance }}"
```

---

## Резервные копии и восстановление

### Автоматизированные ежедневные резервные копии

```bash
#!/bin/bash
# scripts/backup.sh

BACKUP_DIR="/backups/codelab"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Резервная копия PostgreSQL
docker-compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U postgres codelab | gzip > "$BACKUP_DIR/postgres_$DATE.sql.gz"

# Резервная копия MinIO
tar czf "$BACKUP_DIR/minio_$DATE.tar.gz" /var/lib/docker/volumes/minio_data/

# Загрузить на внешнее хранилище (S3, Azure, GCP)
aws s3 sync "$BACKUP_DIR" "s3://your-backup-bucket/codelab/" --delete

# Удалить старые резервные копии (оставить последние 30 дней)
find "$BACKUP_DIR" -mtime +30 -delete
```

Расписание через cron:

```bash
# Редактировать crontab
crontab -e

# Добавить строку (ежедневно в 2 AM)
0 2 * * * /opt/codelab/scripts/backup.sh
```

### Восстановление из резервной копии

```bash
#!/bin/bash
# scripts/restore.sh

BACKUP_FILE=$1

# Остановить сервисы
docker-compose -f docker-compose.prod.yml down

# Восстановить PostgreSQL
docker-compose -f docker-compose.prod.yml up -d postgres
gunzip < "$BACKUP_FILE/postgres_*.sql.gz" | \
  docker-compose -f docker-compose.prod.yml exec postgres \
  psql -U postgres codelab

# Восстановить остальные сервисы
docker-compose -f docker-compose.prod.yml up -d

# Проверить
bash scripts/check-health.sh docker-compose.prod.yml
```

---

## Масштабирование

### Горизонтальное масштабирование

```bash
# Масштабировать Core App на 3 экземпляра
docker-compose -f docker-compose.prod.yml up -d --scale app=3

# Использовать load balancer (Nginx upstream)
```

### Вертикальное масштабирование

Обновить `docker-compose.prod.yml`:

```yaml
app:
  deploy:
    resources:
      limits:
        cpus: '8'
        memory: 4096M
```

---

## Устранение неисправностей

### Сервис не запускается

```bash
# Посмотреть логи
docker-compose -f docker-compose.prod.yml logs <service-name>

# Проверить конфигурацию
docker-compose -f docker-compose.prod.yml config

# Валидировать файл
docker-compose -f docker-compose.prod.yml up --no-start
```

### Проблемы с БД

```bash
# Протестировать PostgreSQL
docker-compose -f docker-compose.prod.yml exec app \
  psql "$DATABASE_URL" -c "SELECT 1"

# Протестировать Redis
docker-compose -f docker-compose.prod.yml exec app \
  redis-cli -u "$REDIS_URL" ping
```

### Проблемы производительности

```bash
# Проверить ресурсы
docker stats

# Проверить дисковое пространство
df -h

# Перезагрузить сервис
docker-compose -f docker-compose.prod.yml restart <service>
```

---

## Плановое обслуживание

### Регулярные задачи

- **Ежедневно**: Проверка логов и здоровья
- **Еженедельно**: Обзор метрик в Grafana
- **Ежемесячно**: Обновление патчей и зависимостей
- **Ежеквартально**: Тестирование восстановления после сбоя

### Процедура обновления

```bash
# Загрузить новые image'и
docker-compose -f docker-compose.prod.yml pull

# Пересобрать и перезагрузить
docker-compose -f docker-compose.prod.yml up -d --no-deps --build <service>

# Проверить
bash scripts/check-health.sh docker-compose.prod.yml
```

---

**Последнее обновление**: 2026-03-13  
**Версия**: 1.0.0  
**Статус**: Production Ready
