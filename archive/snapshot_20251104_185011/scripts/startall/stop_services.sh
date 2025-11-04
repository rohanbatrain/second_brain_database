#!/usr/bin/env bash
set -e

###############################################################################
# Second Brain Database - Stop All Services
###############################################################################

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/../.."
PID_DIR="$PROJECT_ROOT/pids"

log_info "Stopping all services..."
echo -e "${YELLOW}Note: MongoDB runs via Docker and won't be stopped by this script${NC}"

# Stop services by PID files
for pid_file in "$PID_DIR"/*.pid; do
    if [ -f "$pid_file" ]; then
        service_name=$(basename "$pid_file" .pid)
        pid=$(cat "$pid_file")
        
        if kill -0 "$pid" 2>/dev/null; then
            log_info "Stopping $service_name (PID: $pid)..."
            kill "$pid"
            rm "$pid_file"
        else
            log_info "$service_name not running, removing stale PID file"
            rm "$pid_file"
        fi
    fi
done

# Stop Redis
if pgrep -x "redis-server" > /dev/null; then
    log_info "Stopping Redis..."
    redis-cli shutdown 2>/dev/null || pkill redis-server
fi

log_success "All application services stopped"
echo -e "${YELLOW}To stop MongoDB Docker container: docker stop <container_name>${NC}"
