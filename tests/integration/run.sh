#!/bin/bash
# Integration test runner script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Aily Integration Test Framework${NC}"
echo "================================"
echo ""

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: docker-compose not found${NC}"
    exit 1
fi

# Parse arguments
COMMAND="${1:-test}"

case "$COMMAND" in
    up)
        echo -e "${YELLOW}Starting services...${NC}"
        docker-compose up -d
        echo ""
        echo -e "${GREEN}Services started:${NC}"
        echo "  - Feishu Mock:    http://localhost:8001"
        echo "  - Obsidian Mock:  http://localhost:8002"
        echo "  - Browser Service: http://localhost:8003"
        echo ""
        echo "Check status with: ./run.sh status"
        ;;

    down)
        echo -e "${YELLOW}Stopping services...${NC}"
        docker-compose down
        echo -e "${GREEN}Services stopped${NC}"
        ;;

    test)
        echo -e "${YELLOW}Running integration tests...${NC}"
        docker-compose run --rm test-runner "$@"
        ;;

    test-fast)
        echo -e "${YELLOW}Running fast tests only (no slow tests)...${NC}"
        docker-compose run --rm test-runner pytest tests/integration/ -v -m "not slow"
        ;;

    logs)
        SERVICE="${2:-}"
        if [ -n "$SERVICE" ]; then
            docker-compose logs -f "$SERVICE"
        else
            docker-compose logs -f
        fi
        ;;

    status)
        echo -e "${YELLOW}Service status:${NC}"
        docker-compose ps
        echo ""

        # Check health endpoints
        echo -e "${YELLOW}Health checks:${NC}"

        if curl -s http://localhost:8001/health > /dev/null; then
            echo -e "  Feishu Mock:    ${GREEN}✓${NC}"
        else
            echo -e "  Feishu Mock:    ${RED}✗${NC}"
        fi

        if curl -s http://localhost:8002/health > /dev/null; then
            echo -e "  Obsidian Mock:  ${GREEN}✓${NC}"
        else
            echo -e "  Obsidian Mock:  ${RED}✗${NC}"
        fi

        if curl -s http://localhost:8003/health > /dev/null; then
            echo -e "  Browser Service: ${GREEN}✓${NC}"
        else
            echo -e "  Browser Service: ${RED}✗${NC}"
        fi
        ;;

    reset)
        echo -e "${YELLOW}Resetting mock services...${NC}"
        curl -s -X POST http://localhost:8001/__test/reset > /dev/null && echo "  Feishu Mock: reset" || echo "  Feishu Mock: failed"
        curl -s -X POST http://localhost:8002/__test/reset > /dev/null && echo "  Obsidian Mock: reset" || echo "  Obsidian Mock: failed"
        echo -e "${GREEN}Done${NC}"
        ;;

    shell)
        echo -e "${YELLOW}Opening test runner shell...${NC}"
        docker-compose run --rm test-runner bash
        ;;

    build)
        echo -e "${YELLOW}Building all images...${NC}"
        docker-compose build
        echo -e "${GREEN}Build complete${NC}"
        ;;

    clean)
        echo -e "${YELLOW}Cleaning up...${NC}"
        docker-compose down -v
        docker system prune -f
        echo -e "${GREEN}Cleanup complete${NC}"
        ;;

    *)
        echo "Aily Integration Test Runner"
        echo ""
        echo "Usage: ./run.sh [command]"
        echo ""
        echo "Commands:"
        echo "  up          Start all services"
        echo "  down        Stop all services"
        echo "  test        Run all integration tests (default)"
        echo "  test-fast   Run fast tests only (skip slow tests)"
        echo "  logs        Show service logs [service_name]"
        echo "  status      Check service health"
        echo "  reset       Reset mock service state"
        echo "  shell       Open test runner shell"
        echo "  build       Build all Docker images"
        echo "  clean       Stop and clean up everything"
        echo ""
        echo "Examples:"
        echo "  ./run.sh up              # Start services"
        echo "  ./run.sh test            # Run tests"
        echo "  ./run.sh test-fast       # Run fast tests"
        echo "  ./run.sh logs feishu     # View Feishu mock logs"
        ;;
esac
