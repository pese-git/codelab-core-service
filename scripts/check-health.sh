#!/bin/bash

# =============================================================================
# Health Check Script for Production Environment
# =============================================================================
# This script verifies that all services are healthy and properly configured

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
RETRIES=3
TIMEOUT=10
COMPOSE_FILE=${1:-docker-compose.prod.yml}

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}Health Check for CodeLab Production Environment${NC}"
echo -e "${BLUE}==============================================================================${NC}\n"

# Function to check service health
check_service_health() {
    local service_name=$1
    local port=$2
    local check_cmd=$3
    
    echo -n "Checking ${service_name}... "
    
    for ((i=1; i<=RETRIES; i++)); do
        if eval "$check_cmd" &>/dev/null; then
            echo -e "${GREEN}✓ OK${NC}"
            return 0
        fi
        if [ $i -lt $RETRIES ]; then
            sleep 2
        fi
    done
    
    echo -e "${RED}✗ FAILED${NC}"
    return 1
}

# Function to get service status
get_service_status() {
    docker-compose -f "$COMPOSE_FILE" ps $1 2>/dev/null | grep -E "running|exited|Up|Down" | tail -1
}

# Check if docker-compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}Error: Docker Compose file '$COMPOSE_FILE' not found!${NC}"
    exit 1
fi

echo -e "${BLUE}1. Checking Docker Services Status${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

declare -A services
services["postgres"]="5432"
services["redis"]="6379"
services["qdrant"]="6333"
services["clickhouse"]="8123"
services["minio"]="9000"
services["langfuse-worker"]="3030"
services["langfuse-web"]="3001"
services["litellm"]="4000"
services["prometheus"]="9090"
services["grafana"]="3000"
services["jaeger"]="16686"
services["app"]="8000"

for service in "${!services[@]}"; do
    port=${services[$service]}
    echo -n "  $service (port $port): "
    
    if docker ps --filter "name=$service" --format "{{.Names}}" 2>/dev/null | grep -q "$service"; then
        status=$(docker ps --filter "name=$service" --format "{{.Status}}" 2>/dev/null)
        if [[ $status == *"Up"* ]]; then
            echo -e "${GREEN}Running${NC}"
        else
            echo -e "${RED}Not Running (status: $status)${NC}"
        fi
    else
        echo -e "${RED}Container not found${NC}"
    fi
done

echo ""
echo -e "${BLUE}2. Checking Service Health Endpoints${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

FAILED_CHECKS=0

# PostgreSQL
check_service_health "PostgreSQL" "5432" \
    "docker-compose -f $COMPOSE_FILE exec -T postgres pg_isready -U postgres" || ((FAILED_CHECKS++))

# Redis
check_service_health "Redis" "6379" \
    "docker-compose -f $COMPOSE_FILE exec -T redis redis-cli ping" || ((FAILED_CHECKS++))

# Qdrant
check_service_health "Qdrant" "6333" \
    "curl -sf http://localhost:6333/health >/dev/null" || ((FAILED_CHECKS++))

# ClickHouse
check_service_health "ClickHouse" "8123" \
    "curl -sf http://localhost:8123/ping >/dev/null" || ((FAILED_CHECKS++))

# MinIO
check_service_health "MinIO" "9000" \
    "curl -sf http://localhost:9000/minio/health/live >/dev/null" || ((FAILED_CHECKS++))

# Langfuse Worker
check_service_health "Langfuse Worker" "3030" \
    "curl -sf http://localhost:3030/health >/dev/null" || ((FAILED_CHECKS++))

# Langfuse Web
check_service_health "Langfuse Web" "3001" \
    "curl -sf http://localhost:3001/ >/dev/null" || ((FAILED_CHECKS++))

# LiteLLM
check_service_health "LiteLLM" "4000" \
    "curl -sf http://localhost:4000/health/readiness >/dev/null" || ((FAILED_CHECKS++))

# Prometheus
check_service_health "Prometheus" "9090" \
    "curl -sf http://localhost:9090/-/healthy >/dev/null" || ((FAILED_CHECKS++))

# Grafana
check_service_health "Grafana" "3000" \
    "curl -sf http://localhost:3000/api/health >/dev/null" || ((FAILED_CHECKS++))

# Jaeger
check_service_health "Jaeger" "16686" \
    "curl -sf http://localhost:16686/api/services >/dev/null" || ((FAILED_CHECKS++))

# Core App
check_service_health "Core App" "8000" \
    "curl -sf http://localhost:8000/health >/dev/null" || ((FAILED_CHECKS++))

echo ""
echo -e "${BLUE}3. Checking Resource Usage${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "Container Resource Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null | grep -E "codelab-" || true

echo ""
echo -e "${BLUE}4. Checking Volume Status${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

volumes=("postgres_data" "redis_data" "qdrant_data" "prometheus_data" "grafana_data" "clickhouse_data" "minio_data")

for volume in "${volumes[@]}"; do
    if docker volume ls --format "{{.Name}}" 2>/dev/null | grep -q "^${volume}$"; then
        size=$(docker volume inspect "$volume" --format "{{json .Mountpoint}}" 2>/dev/null | tr -d '"')
        echo -e "  $volume: ${GREEN}✓ Exists${NC}"
    else
        echo -e "  $volume: ${YELLOW}⚠ Missing${NC}"
    fi
done

echo ""
echo -e "${BLUE}5. Checking Configuration${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check for environment file
if [ -f ".env.production" ]; then
    echo -e "  .env.production file: ${GREEN}✓ Found${NC}"
    
    # Check for required variables
    required_vars=("POSTGRES_PASSWORD" "REDIS_PASSWORD" "MINIO_ROOT_PASSWORD")
    for var in "${required_vars[@]}"; do
        if grep -q "^${var}=" .env.production; then
            value=$(grep "^${var}=" .env.production | cut -d'=' -f2)
            if [ -z "$value" ] || [ "$value" = "change-me-"* ]; then
                echo -e "  $var: ${YELLOW}⚠ Not configured (using default)${NC}"
            else
                echo -e "  $var: ${GREEN}✓ Configured${NC}"
            fi
        else
            echo -e "  $var: ${RED}✗ Missing${NC}"
        fi
    done
else
    echo -e "  .env.production file: ${YELLOW}⚠ Not found (using defaults)${NC}"
fi

echo ""
echo -e "${BLUE}6. Summary${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $FAILED_CHECKS -eq 0 ]; then
    echo -e "${GREEN}✓ All services are healthy!${NC}"
    echo ""
    echo "Service URLs:"
    echo "  - Langfuse UI:  http://localhost:3001"
    echo "  - Grafana:      http://localhost:3000"
    echo "  - Jaeger:       http://localhost:16686"
    echo "  - Prometheus:   http://localhost:9090"
    echo "  - MinIO:        http://localhost:9001"
    echo "  - Core App:     http://localhost:8000"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Health check found $FAILED_CHECKS failing services${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check logs: docker-compose -f $COMPOSE_FILE logs <service-name>"
    echo "  2. Restart services: docker-compose -f $COMPOSE_FILE restart"
    echo "  3. View running services: docker-compose -f $COMPOSE_FILE ps"
    echo ""
    exit 1
fi
