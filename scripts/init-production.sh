#!/bin/bash

# =============================================================================
# Production Initialization Script
# =============================================================================
# This script initializes the production environment for the first time

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}CodeLab Production Environment Initialization${NC}"
echo -e "${BLUE}==============================================================================${NC}\n"

# Check if .env.production exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}⚠ .env.production file not found!${NC}"
    echo "Creating from .env.production.example..."
    
    if [ ! -f ".env.production.example" ]; then
        echo -e "${RED}✗ .env.production.example not found!${NC}"
        exit 1
    fi
    
    cp .env.production.example "$ENV_FILE"
    echo -e "${GREEN}✓ Created $ENV_FILE${NC}"
    echo ""
    echo -e "${YELLOW}⚠ IMPORTANT: Please edit $ENV_FILE and set all 'change-me-*' values${NC}"
    echo "Required changes:"
    echo "  - POSTGRES_PASSWORD"
    echo "  - REDIS_PASSWORD"
    echo "  - MINIO_ROOT_PASSWORD"
    echo "  - CLICKHOUSE_PASSWORD"
    echo "  - NEXTAUTH_SECRET"
    echo "  - LITELLM_MASTER_KEY"
    echo "  - All other 'change-me-*' values"
    echo ""
    exit 1
fi

echo -e "${BLUE}Step 1: Validating Configuration${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check for required variables
required_vars=(
    "POSTGRES_PASSWORD"
    "REDIS_PASSWORD"
    "MINIO_ROOT_PASSWORD"
    "CLICKHOUSE_PASSWORD"
    "NEXTAUTH_SECRET"
    "ENCRYPTION_KEY"
    "LITELLM_MASTER_KEY"
)

missing_vars=0
for var in "${required_vars[@]}"; do
    if grep -q "^${var}=" "$ENV_FILE"; then
        value=$(grep "^${var}=" "$ENV_FILE" | cut -d'=' -f2-)
        if [[ "$value" == "change-me"* ]] || [ -z "$value" ]; then
            echo -e "  ${YELLOW}⚠ $var${NC} - NOT CONFIGURED (using placeholder)"
            ((missing_vars++))
        else
            echo -e "  ${GREEN}✓ $var${NC} - Configured"
        fi
    else
        echo -e "  ${RED}✗ $var${NC} - MISSING from $ENV_FILE"
        ((missing_vars++))
    fi
done

if [ $missing_vars -gt 0 ]; then
    echo ""
    echo -e "${RED}✗ Found $missing_vars configuration issues!${NC}"
    echo "Please edit $ENV_FILE and set all required values."
    exit 1
fi

echo -e "${GREEN}✓ All required variables are configured${NC}\n"

# Check if Docker is running
echo -e "${BLUE}Step 2: Checking Docker${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ! docker --version &>/dev/null; then
    echo -e "${RED}✗ Docker is not installed!${NC}"
    exit 1
fi

if ! docker ps &>/dev/null; then
    echo -e "${RED}✗ Docker daemon is not running!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker is available${NC}\n"

# Check if docker-compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}✗ $COMPOSE_FILE not found!${NC}"
    exit 1
fi

echo -e "${BLUE}Step 3: Stopping Existing Containers${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if docker-compose -f "$COMPOSE_FILE" ps 2>/dev/null | grep -q "codelab-"; then
    echo "Stopping running containers..."
    docker-compose -f "$COMPOSE_FILE" down --remove-orphans || true
    echo -e "${GREEN}✓ Containers stopped${NC}"
else
    echo -e "${GREEN}✓ No running containers${NC}"
fi

echo ""

# Clean up volumes (optional - only if explicitly requested)
if [ "$1" = "--clean" ] || [ "$1" = "-c" ]; then
    echo -e "${YELLOW}⚠ Cleaning volumes (this will delete all data)${NC}"
    docker-compose -f "$COMPOSE_FILE" down -v --remove-orphans
    echo -e "${GREEN}✓ Volumes cleaned${NC}"
    echo ""
fi

echo -e "${BLUE}Step 4: Building Images${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docker-compose -f "$COMPOSE_FILE" build --no-cache
echo -e "${GREEN}✓ Images built${NC}\n"

echo -e "${BLUE}Step 5: Starting Services${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docker-compose -f "$COMPOSE_FILE" up -d --wait

echo -e "${GREEN}✓ All services started${NC}\n"

echo -e "${BLUE}Step 6: Waiting for Services to be Ready${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Wait for core dependencies
services=("postgres" "redis" "clickhouse" "minio")
for service in "${services[@]}"; do
    echo "Waiting for $service..."
    docker-compose -f "$COMPOSE_FILE" exec -T "$service" true &>/dev/null || true
done

# Wait for database migrations to complete
echo "Waiting for database migrations..."
sleep 15

echo -e "${GREEN}✓ Services are ready${NC}\n"

echo -e "${BLUE}Step 7: Running Health Checks${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -x "scripts/check-health.sh" ]; then
    bash scripts/check-health.sh "$COMPOSE_FILE" || true
else
    echo -e "${YELLOW}⚠ Health check script not found${NC}"
fi

echo ""
echo -e "${BLUE}==============================================================================${NC}"
echo -e "${GREEN}✓ Production initialization complete!${NC}"
echo -e "${BLUE}==============================================================================${NC}\n"

echo "Next steps:"
echo "  1. Verify all services are healthy: bash scripts/check-health.sh"
echo "  2. Access Langfuse: http://localhost:3001"
echo "  3. Access Grafana: http://localhost:3000"
echo "  4. Configure your firewall and reverse proxy"
echo "  5. Enable HTTPS with Let's Encrypt"
echo "  6. Set up automated backups"
echo "  7. Configure monitoring and alerting"
echo ""
echo "Important URLs:"
echo "  - Langfuse UI:  http://localhost:3001"
echo "  - Grafana:      http://localhost:3000"
echo "  - Jaeger:       http://localhost:16686"
echo "  - Prometheus:   http://localhost:9090"
echo "  - MinIO:        http://localhost:9001"
echo "  - Core App:     http://localhost:8000"
echo ""
echo "Useful commands:"
echo "  - View logs:    docker-compose -f $COMPOSE_FILE logs -f <service>"
echo "  - Stop all:     docker-compose -f $COMPOSE_FILE down"
echo "  - Restart all:  docker-compose -f $COMPOSE_FILE restart"
echo "  - Scale service: docker-compose -f $COMPOSE_FILE up -d --scale app=3"
echo ""
