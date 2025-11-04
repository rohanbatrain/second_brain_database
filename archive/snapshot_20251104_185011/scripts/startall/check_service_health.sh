#!/usr/bin/env bash

###############################################################################
# Second Brain Database - Service Health Check
#
# Quickly check the status of all services
###############################################################################

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/../.."
PID_DIR="$PROJECT_ROOT/pids"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Second Brain Database - Service Health Check            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

check_port() {
    local port=$1
    local service=$2
    
    if nc -z localhost "$port" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $service (port $port)"
        return 0
    else
        echo -e "${RED}✗${NC} $service (port $port) - NOT RESPONDING"
        return 1
    fi
}

check_process() {
    local pid_file=$1
    local service=$2
    
    if [ ! -f "$pid_file" ]; then
        echo -e "${RED}✗${NC} $service - PID file not found"
        return 1
    fi
    
    local pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $service (PID: $pid)"
        return 0
    else
        echo -e "${RED}✗${NC} $service (PID: $pid) - NOT RUNNING"
        return 1
    fi
}

echo -e "${BLUE}Infrastructure Services:${NC}"
echo "─────────────────────────"
check_port 27017 "MongoDB (Docker)"
check_port 6379 "Redis"
check_port 11434 "Ollama"
check_port 7880 "LiveKit"
echo ""

echo -e "${BLUE}Application Services:${NC}"
echo "─────────────────────────"
check_port 8000 "FastAPI"
check_process "$PID_DIR/voice_worker.pid" "Voice Worker"
check_process "$PID_DIR/celery_worker.pid" "Celery Worker"
check_process "$PID_DIR/celery_beat.pid" "Celery Beat"
check_port 5555 "Flower"
echo ""

echo -e "${BLUE}Service URLs:${NC}"
echo "─────────────────────────"
echo "  API:     http://localhost:8000/docs"
echo "  Flower:  http://localhost:5555"
echo "  Ollama:  http://localhost:11434"
echo ""

echo -e "${BLUE}Quick Actions:${NC}"
echo "─────────────────────────"
echo "  View logs:     ./scripts/startall/attach_service.sh"
echo "  Restart all:   ./stop.sh && ./start.sh"
echo "  Stop all:      ./stop.sh"
echo ""

# Check for errors in recent logs
echo -e "${BLUE}Recent Errors:${NC}"
echo "─────────────────────────"
error_count=$(find logs/ -name "*.log" -mmin -5 -exec grep -i error {} + 2>/dev/null | wc -l | tr -d ' ')
if [ "$error_count" -gt 0 ]; then
    echo -e "${YELLOW}⚠${NC} Found $error_count errors in last 5 minutes"
    echo "  View with: grep -i error logs/*.log | tail -20"
else
    echo -e "${GREEN}✓${NC} No errors in last 5 minutes"
fi
echo ""
