#!/bin/bash
# Run REAL service integration tests (NO MOCKS)
# These tests hit production services and have real side effects

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Aily Real Service Integration Tests${NC}"
echo "===================================="
echo ""

# Check for venv
if [ ! -d ".venv" ]; then
    echo -e "${RED}Error: .venv not found${NC}"
    echo "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate venv
source .venv/bin/activate

# Check service availability
echo -e "${YELLOW}Checking service configuration...${NC}"

FEISHU_READY=false
OBSIDIAN_READY=false

if [ -n "$FEISHU_APP_ID" ] && [ -n "$FEISHU_APP_SECRET" ]; then
    echo -e "  Feishu: ${GREEN}✓ configured${NC}"
    FEISHU_READY=true
else
    echo -e "  Feishu: ${RED}✗ missing FEISHU_APP_ID or FEISHU_APP_SECRET${NC}"
fi

if [ -n "$OBSIDIAN_VAULT_PATH" ] && [ -n "$OBSIDIAN_REST_API_KEY" ]; then
    echo -e "  Obsidian: ${GREEN}✓ configured${NC}"
    OBSIDIAN_READY=true
else
    echo -e "  Obsidian: ${RED}✗ missing OBSIDIAN_VAULT_PATH or OBSIDIAN_REST_API_KEY${NC}"
fi

echo ""

# Show warnings
if [ "$FEISHU_READY" = true ]; then
    echo -e "${YELLOW}⚠️  WARNING: Feishu tests will send REAL messages${NC}"
fi

if [ "$OBSIDIAN_READY" = true ]; then
    echo -e "${YELLOW}⚠️  WARNING: Obsidian tests will write REAL files${NC}"
fi

echo ""

# Parse command
COMMAND="${1:-test}"
shift || true  # Remove command from args so $@ contains only extra args

case "$COMMAND" in
    test)
        echo -e "${BLUE}Running real service tests...${NC}"
        pytest tests/integration/test_real_services.py -v -s "$@"
        ;;

    feishu)
        echo -e "${BLUE}Running Feishu tests only...${NC}"
        pytest tests/integration/test_real_services.py::TestRealFeishuExposesProblems -v -s
        ;;

    obsidian)
        echo -e "${BLUE}Running Obsidian tests only...${NC}"
        pytest tests/integration/test_real_services.py::TestRealObsidianExposesProblems -v -s
        ;;

    browser)
        echo -e "${BLUE}Running Browser tests only...${NC}"
        pytest tests/integration/test_real_services.py::TestRealBrowserExposesProblems -v -s
        ;;

    db)
        echo -e "${BLUE}Running Database tests only...${NC}"
        pytest tests/integration/test_real_services.py::TestDatabaseExposesProblems -v -s
        ;;

    e2e)
        echo -e "${BLUE}Running E2E MVP tests...${NC}"
        echo ""
        echo "Testing Aily's core value: Send link → Get structured knowledge"
        echo ""
        pytest tests/integration/test_e2e_mvp.py -v -s "$@"
        ;;

    visual)
        echo -e "${BLUE}Running Visual E2E tests...${NC}"
        echo ""
        echo "Capturing screenshots and screen recordings..."
        echo "Artifacts saved to: test-artifacts/"
        echo ""
        pytest tests/integration/test_e2e_visual.py -v -s "$@"
        ;;

    tavily)
        echo -e "${BLUE}Running Tavily Search tests...${NC}"
        echo ""
        echo "Testing AI search API..."
        echo ""
        pytest tests/integration/test_tavily_search.py -v -s
        ;;

    verify)
        echo -e "${BLUE}Running Claim Verification tests...${NC}"
        echo ""
        echo "Testing source verification like a human researcher..."
        echo ""
        pytest tests/integration/test_verification.py -v -s
        ;;

    check)
        echo -e "${GREEN}Configuration check complete${NC}"
        ;;

    *)
        echo "Real Service Test Runner"
        echo ""
        echo "Usage: ./run-real.sh [command]"
        echo ""
        echo "Commands:"
        echo "  test       Run all real service tests (default)"
        echo "  e2e        Run E2E MVP tests (core value validation)"
        echo "  visual     Run Visual tests (screenshots + video)"
        echo "  feishu     Run Feishu tests only"
        echo "  obsidian   Run Obsidian tests only"
        echo "  browser    Run Browser tests only"
        echo "  db         Run Database tests only"
        echo "  check      Just check configuration, don't run tests"
        echo ""
        echo "Examples:"
        echo "  ./run-real.sh              # Run all tests"
        echo "  ./run-real.sh e2e          # Test core value (link → note)"
        echo "  ./run-real.sh visual       # Capture visual artifacts"
        echo "  ./run-real.sh feishu       # Test Feishu only"
        echo "  ./run-real.sh test -x      # Stop on first failure"
        ;;
esac
