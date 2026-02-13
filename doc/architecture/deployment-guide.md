# Руководство по развертыванию

## Содержание
- [Требования](#требования)
- [Локальная разработка](#локальная-разработка)
- [Docker Compose](#docker-compose)
- [Kubernetes](#kubernetes)
- [Мониторинг](#мониторинг)
- [Резервное копирование](#резервное-копирование)
- [Troubleshooting](#troubleshooting)

---

## Требования

### Минимальные требования

| Компонент | Требование |
|-----------|------------|
| CPU | 4 cores |
| RAM | 8 GB |
| Disk | 50 GB SSD |
| OS | Linux (Ubuntu 22.04+), macOS 12+, Windows 11 |
| Python | 3.12+ |
| Docker | 24.0+ |
| Docker Compose | 2.20+ |

### Рекомендуемые требования (Production)

| Компонент | Требование |
|-----------|------------|
| CPU | 8+ cores |
| RAM | 32 GB |
| Disk | 500 GB SSD (NVMe) |
| Network | 1 Gbps |
| Kubernetes | 1.28+ |

---

## Локальная разработка

### 1. Установка зависимостей

#### Установка uv (менеджер пакетов)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex
```

#### Клонирование репозитория

```bash
git clone https://github.com/your-org/codelab-core-service.git
cd codelab-core-service
```

#### Установка Python зависимостей

```bash
# Создание виртуального окружения и установка зависимостей
uv pip install -e ".[dev]"
```

### 2. Настройка окружения

```bash
# Копирование примера конфигурации
cp .env.example .env

# Редактирование .env
nano .env
```

**Обязательные переменные**:
```bash
# OpenAI API (обязательно!)
OPENAI_API_KEY=sk-your-openai-api-key

# JWT Secret (обязательно для production!)
JWT_SECRET_KEY=your-secret-key-change-in-production

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/codelab

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant
QDRANT_URL=http://localhost:6333
```

### 3. Запуск инфраструктуры

```bash
# Запуск только БД сервисов (без приложения)
docker-compose -f docker-compose.dev.yml up -d postgres redis qdrant

# Проверка статуса
docker-compose -f docker-compose.dev.yml ps
```

### 4. Инициализация базы данных

```bash
# Применение миграций
alembic upgrade head

# Создание тестовых данных (опционально)
python scripts/init_db.py seed
```

### 5. Запуск приложения

```bash
# С hot-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Или через make
make dev
```

### 6. Проверка работоспособности

```bash
# Health check
curl http://localhost:8000/health

# API документация
open http://localhost:8000/docs
```

---

## Docker Compose

### Архитектура развертывания

```mermaid
graph TB
    subgraph "Docker Compose Stack"
        subgraph "Application"
            App[FastAPI App<br/>Port: 8000]
        end
        
        subgraph "Databases"
            PG[PostgreSQL 16<br/>Port: 5432]
            Redis[Redis 7<br/>Port: 6379]
            Qdrant[Qdrant<br/>Port: 6333]
        end
        
        subgraph "Monitoring (Optional)"
            Prom[Prometheus<br/>Port: 9090]
            Graf[Grafana<br/>Port: 3000]
        end
    end
    
    App --> PG
    App --> Redis
    App --> Qdrant
    Prom --> App
    Graf --> Prom
```

### Development Stack

**Файл**: `docker-compose.dev.yml`

```bash
# Запуск
docker-compose -f docker-compose.dev.yml up -d

# Просмотр логов
docker-compose -f docker-compose.dev.yml logs -f app

# Остановка
docker-compose -f docker-compose.dev.yml down

# Остановка с удалением volumes (УДАЛИТ ВСЕ ДАННЫЕ!)
docker-compose -f docker-compose.dev.yml down -v
```

**Сервисы**:
- `app` - FastAPI приложение
- `postgres` - PostgreSQL 16
- `redis` - Redis 7
- `qdrant` - Qdrant

### Production Stack

**Файл**: `docker-compose.yml`

```bash
# Запуск полного стека
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов всех сервисов
docker-compose logs -f

# Перезапуск конкретного сервиса
docker-compose restart app
```

**Дополнительные сервисы**:
- `prometheus` - Сбор метрик
- `grafana` - Визуализация метрик

### Управление volumes

```bash
# Список volumes
docker volume ls | grep codelab

# Резервное копирование PostgreSQL
docker-compose exec postgres pg_dump -U postgres codelab > backup.sql

# Восстановление PostgreSQL
docker-compose exec -T postgres psql -U postgres codelab < backup.sql

# Очистка неиспользуемых volumes
docker volume prune
```

### Обновление образов

```bash
# Пересборка образов
docker-compose build --no-cache

# Обновление и перезапуск
docker-compose pull
docker-compose up -d
```

---

## Kubernetes

### Архитектура Kubernetes

```mermaid
graph TB
    subgraph "Kubernetes Cluster"
        subgraph "Ingress Layer"
            Ingress[Ingress Controller<br/>nginx/traefik]
            Cert[Cert Manager<br/>Let's Encrypt]
        end
        
        subgraph "Application Layer"
            Deploy[Deployment: api<br/>Replicas: 3+]
            HPA[HorizontalPodAutoscaler]
            Service[Service: api-service]
        end
        
        subgraph "Data Layer"
            PGSts[StatefulSet: postgres]
            RedisSts[StatefulSet: redis]
            QdrantSts[StatefulSet: qdrant]
        end
        
        subgraph "Storage"
            PVC1[PVC: postgres-data]
            PVC2[PVC: redis-data]
            PVC3[PVC: qdrant-data]
        end
        
        subgraph "Monitoring"
            PromOp[Prometheus Operator]
            ServiceMon[ServiceMonitor]
        end
    end
    
    Internet[Internet] --> Ingress
    Ingress --> Service
    Service --> Deploy
    HPA --> Deploy
    
    Deploy --> PGSts
    Deploy --> RedisSts
    Deploy --> QdrantSts
    
    PGSts --> PVC1
    RedisSts --> PVC2
    QdrantSts --> PVC3
    
    PromOp --> ServiceMon
    ServiceMon --> Deploy
```

### Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: codelab
  labels:
    name: codelab
    environment: production
```

### ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: codelab-config
  namespace: codelab
data:
  APP_ENV: "production"
  LOG_LEVEL: "INFO"
  DATABASE_URL: "postgresql+asyncpg://postgres:postgres@postgres-service:5432/codelab"
  REDIS_URL: "redis://redis-service:6379/0"
  QDRANT_URL: "http://qdrant-service:6333"
```

### Secrets

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: codelab-secrets
  namespace: codelab
type: Opaque
stringData:
  OPENAI_API_KEY: "sk-your-openai-api-key"
  JWT_SECRET_KEY: "your-secret-key-change-in-production"
  DATABASE_PASSWORD: "secure-password"
```

**Создание из командной строки**:
```bash
kubectl create secret generic codelab-secrets \
  --from-literal=OPENAI_API_KEY=sk-xxx \
  --from-literal=JWT_SECRET_KEY=xxx \
  -n codelab
```

### Deployment (API)

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: codelab
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: your-registry/codelab-core-service:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: codelab-config
        - secretRef:
            name: codelab-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

### Service

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: api-service
  namespace: codelab
spec:
  selector:
    app: api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

### HorizontalPodAutoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
  namespace: codelab
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Ingress

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  namespace: codelab
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.codelab.example.com
    secretName: codelab-tls
  rules:
  - host: api.codelab.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
```

### StatefulSet (PostgreSQL)

```yaml
# k8s/postgres-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: codelab
spec:
  serviceName: postgres-service
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:16
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: codelab
        - name: POSTGRES_USER
          value: postgres
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: codelab-secrets
              key: DATABASE_PASSWORD
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
  volumeClaimTemplates:
  - metadata:
      name: postgres-data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 100Gi
```

### Развертывание

```bash
# Создание namespace
kubectl apply -f k8s/namespace.yaml

# Создание secrets
kubectl apply -f k8s/secrets.yaml

# Создание configmap
kubectl apply -f k8s/configmap.yaml

# Развертывание баз данных
kubectl apply -f k8s/postgres-statefulset.yaml
kubectl apply -f k8s/redis-statefulset.yaml
kubectl apply -f k8s/qdrant-statefulset.yaml

# Ожидание готовности БД
kubectl wait --for=condition=ready pod -l app=postgres -n codelab --timeout=300s

# Применение миграций
kubectl run -it --rm migrate \
  --image=your-registry/codelab-core-service:latest \
  --restart=Never \
  --namespace=codelab \
  --command -- alembic upgrade head

# Развертывание приложения
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/ingress.yaml

# Проверка статуса
kubectl get all -n codelab
```

### Мониторинг развертывания

```bash
# Статус pods
kubectl get pods -n codelab -w

# Логи приложения
kubectl logs -f deployment/api -n codelab

# Описание pod
kubectl describe pod <pod-name> -n codelab

# Exec в pod
kubectl exec -it <pod-name> -n codelab -- /bin/bash

# Метрики HPA
kubectl get hpa -n codelab -w
```

---

## Мониторинг

### Prometheus

#### ServiceMonitor

```yaml
# k8s/servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: api-monitor
  namespace: codelab
spec:
  selector:
    matchLabels:
      app: api
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
```

#### Основные метрики

```promql
# HTTP Request Rate
rate(http_requests_total[5m])

# HTTP Request Duration (P95)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error Rate
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# Database Connection Pool
db_connection_pool_size
db_connection_pool_available

# Agent Tasks
agent_tasks_queued
agent_tasks_running
agent_tasks_completed_total
agent_tasks_failed_total

# SSE Connections
sse_connections_active
sse_connections_total
```

### Grafana

#### Дашборды

1. **Application Overview**
   - Request rate, latency, error rate
   - Active connections
   - Resource usage (CPU, Memory)

2. **Database Performance**
   - Query latency
   - Connection pool usage
   - Slow queries

3. **Agent Performance**
   - Tasks queued/running/completed
   - Agent response time
   - Context search latency

4. **Error Tracking**
   - Error rate by endpoint
   - Error types distribution
   - Recent errors log

### Алерты

```yaml
# prometheus-rules.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: codelab-alerts
  namespace: codelab
spec:
  groups:
  - name: codelab
    interval: 30s
    rules:
    - alert: HighErrorRate
      expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "High error rate detected"
        description: "Error rate is {{ $value }} (threshold: 0.05)"
    
    - alert: HighLatency
      expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High latency detected"
        description: "P95 latency is {{ $value }}s (threshold: 2s)"
    
    - alert: DatabaseConnectionPoolExhausted
      expr: db_connection_pool_available == 0
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "Database connection pool exhausted"
```

---

## Резервное копирование

### PostgreSQL

#### Автоматическое резервное копирование

```bash
# Скрипт резервного копирования
#!/bin/bash
BACKUP_DIR="/backups/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/codelab_$TIMESTAMP.sql.gz"

# Создание резервной копии
kubectl exec -n codelab postgres-0 -- \
  pg_dump -U postgres codelab | gzip > $BACKUP_FILE

# Удаление старых копий (старше 7 дней)
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup created: $BACKUP_FILE"
```

#### CronJob для автоматизации

```yaml
# k8s/backup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: codelab
spec:
  schedule: "0 2 * * *"  # Каждый день в 2:00
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:16
            command:
            - /bin/sh
            - -c
            - |
              pg_dump -h postgres-service -U postgres codelab | \
              gzip > /backups/codelab_$(date +%Y%m%d_%H%M%S).sql.gz
            volumeMounts:
            - name: backup-storage
              mountPath: /backups
          restartPolicy: OnFailure
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
```

### Qdrant

```bash
# Создание snapshot
kubectl exec -n codelab qdrant-0 -- \
  curl -X POST http://localhost:6333/collections/user123_coder_context/snapshots

# Скачивание snapshot
kubectl cp codelab/qdrant-0:/qdrant/snapshots/snapshot.tar ./backup/
```

---

## Troubleshooting

### Проблема: Pods не запускаются

```bash
# Проверка событий
kubectl get events -n codelab --sort-by='.lastTimestamp'

# Описание pod
kubectl describe pod <pod-name> -n codelab

# Логи init containers
kubectl logs <pod-name> -c init-container -n codelab
```

**Частые причины**:
- Недостаточно ресурсов (CPU/Memory)
- Проблемы с образом (ImagePullBackOff)
- Неверные secrets/configmaps
- Проблемы с volumes

### Проблема: Высокая latency

```bash
# Проверка метрик
kubectl top pods -n codelab

# Проверка HPA
kubectl get hpa -n codelab

# Увеличение replicas вручную
kubectl scale deployment api --replicas=5 -n codelab
```

### Проблема: Database connection errors

```bash
# Проверка статуса PostgreSQL
kubectl exec -n codelab postgres-0 -- pg_isready

# Проверка соединений
kubectl exec -n codelab postgres-0 -- \
  psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Перезапуск PostgreSQL
kubectl rollout restart statefulset postgres -n codelab
```

### Проблема: Out of Memory

```bash
# Проверка использования памяти
kubectl top pods -n codelab

# Увеличение лимитов
kubectl set resources deployment api \
  --limits=memory=4Gi \
  -n codelab

# Проверка memory leaks
kubectl exec -it <pod-name> -n codelab -- python -m memory_profiler
```

### Логи и отладка

```bash
# Логи с фильтрацией
kubectl logs -f deployment/api -n codelab | grep ERROR

# Логи всех pods
kubectl logs -l app=api -n codelab --tail=100

# Exec в pod для отладки
kubectl exec -it <pod-name> -n codelab -- /bin/bash

# Port forwarding для локальной отладки
kubectl port-forward svc/api-service 8000:80 -n codelab
```

---

## Checklist развертывания

### Pre-deployment

- [ ] Проверены все переменные окружения
- [ ] Созданы secrets с реальными значениями
- [ ] Настроены DNS записи
- [ ] Подготовлены SSL сертификаты
- [ ] Проверена доступность Docker registry
- [ ] Созданы резервные копии (если обновление)

### Deployment

- [ ] Применены миграции базы данных
- [ ] Развернуты StatefulSets (БД)
- [ ] Развернут Deployment (API)
- [ ] Настроен Ingress
- [ ] Настроен HPA
- [ ] Проверены health checks

### Post-deployment

- [ ] Проверена доступность API
- [ ] Проверены логи на ошибки
- [ ] Настроены алерты
- [ ] Проверены метрики в Grafana
- [ ] Выполнены smoke tests
- [ ] Обновлена документация

---

## Дополнительные ресурсы

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
