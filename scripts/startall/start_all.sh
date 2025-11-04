#!/usr/bin/env bash
# Production-ready startup with error recovery
# DO NOT use 'set -e' - we handle errors gracefully

###############################################################################
# Second Brain Database - Unified Production Startup Script
#
# Starts all required services:
# - MongoDB
# - Redis
# - Ollama
# - LiveKit
# - FastAPI Server
# - LiveKit Voice Worker
# - Celery Worker
# - Celery Beat
# - Flower Dashboard
###############################################################################

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    if [ "$DEBUG" = "1" ]; then
        echo -e "${CYAN}[DEBUG]${NC} $1"
    fi
}

# Check command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/../.."
cd "$PROJECT_ROOT"

# Load environment variables from .sbd (our config file) and .env
if [ -f ".sbd" ]; then
    echo "Loading configuration from .sbd"
    export $(grep -v '^#' .sbd | grep -v '^$' | xargs)
fi

if [ -f ".env" ]; then
    echo "Loading configuration from .env"
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi

# Use uv for Python commands
PYTHON_CMD="uv run python"

# Create logs directory
mkdir -p logs

# PID file directory
PID_DIR="$PROJECT_ROOT/pids"
mkdir -p "$PID_DIR"

# Track failures
FAILED_SERVICES=()
CRITICAL_FAILURES=()
STARTED_SERVICES=()
STARTUP_LOG="$PROJECT_ROOT/logs/startup_$(date +%Y%m%d_%H%M%S).log"

# Redirect all output to both console and log file
exec > >(tee -a "$STARTUP_LOG")
exec 2>&1

###############################################################################
# Cleanup on Failure
###############################################################################

cleanup_on_failure() {
    log_error "Stopping all services due to failure..."
    
    # Stop all services that were started
    for service in "${STARTED_SERVICES[@]}"; do
        log_info "Stopping $service..."
        case $service in
            "redis")
                redis-cli shutdown 2>/dev/null || true
                ;;
            "ollama")
                if [ -f "$PID_DIR/ollama.pid" ]; then
                    kill $(cat "$PID_DIR/ollama.pid") 2>/dev/null || true
                    rm -f "$PID_DIR/ollama.pid"
                fi
                ;;

        esac
    done
    
    log_error "All services stopped due to startup failure"
    exit 1
}

###############################################################################
# Port Cleanup
###############################################################################

cleanup_port() {
    local port=$1
    local service_name=$2
    local expected_process=$3  # Optional: expected process name/pattern (can use | for alternatives)
    
    if command_exists lsof; then
        local pids=$(lsof -ti:$port 2>/dev/null)
        if [ ! -z "$pids" ]; then
            # Check if it's already our desired service
            if [ ! -z "$expected_process" ]; then
                local is_correct_service=false
                for pid in $pids; do
                    if [ ! -z "$pid" ]; then
                        local process_cmd=$(ps -p $pid -o comm= 2>/dev/null || echo "")
                        local process_args=$(ps -p $pid -o args= 2>/dev/null || echo "")
                        local full_info="$process_cmd $process_args"
                        
                        # Check if process matches expected service (supports regex with |)
                        if echo "$full_info" | grep -qE "$expected_process"; then
                            log_success "Port $port already in use by $service_name (PID: $pid) - skipping cleanup"
                            return 0
                        fi
                    fi
                done
            fi
            
            log_warning "Port $port is in use by a different process (needed for $service_name)"
            log_info "Killing processes on port $port..."
            
            # Kill all PIDs on this port
            for pid in $pids; do
                if [ ! -z "$pid" ]; then
                    log_debug "Killing PID $pid on port $port"
                    kill -9 $pid 2>/dev/null || true
                fi
            done
            
            sleep 1
            
            # Verify port is free
            if lsof -ti:$port >/dev/null 2>&1; then
                log_error "Failed to free port $port"
                return 1
            fi
            log_success "Port $port is now free"
        fi
    fi
    return 0
}

cleanup_all_ports() {
    log_info "Checking for port conflicts..."
    
    # Common ports used by our services (port, service_name, expected_process)
    # Note: Docker processes may show as "com.docke" or "docker-proxy"
    # Note: Voice worker (8081) is NOT cleaned here - managed by Python code
    cleanup_port 6379 "Redis" "redis-server" || return 1
    cleanup_port 27017 "MongoDB" "mongod|com.docke|docker" || return 1
    cleanup_port 11434 "Ollama" "ollama" || return 1
    cleanup_port 8000 "FastAPI" "uvicorn" || return 1
    # cleanup_port 8081 "Voice Worker" "start_voice_worker|python.*voice_worker" || return 1  # Managed by Python
    cleanup_port 5555 "Flower" "flower" || return 1
    
    log_success "All ports checked and cleaned"
    return 0
}

###############################################################################
# Service Health Checks
###############################################################################

wait_for_port() {
    local port=$1
    local service=$2
    local max_wait=${3:-30}
    local count=0
    
    log_info "Waiting for $service on port $port..."
    while ! nc -z localhost "$port" 2>/dev/null; do
        sleep 1
        count=$((count + 1))
        if [ $count -ge $max_wait ]; then
            log_error "$service did not start within ${max_wait}s"
            return 1
        fi
    done
    log_success "$service is responding on port $port"
    return 0
}

check_process_health() {
    local pid_file=$1
    local service=$2
    
    if [ ! -f "$pid_file" ]; then
        log_debug "PID file not found: $pid_file"
        return 1
    fi
    
    local pid=$(cat "$pid_file")
    if ! kill -0 "$pid" 2>/dev/null; then
        log_debug "Process $pid not running for $service"
        return 1
    fi
    
    return 0
}

###############################################################################
# Service Management Functions
###############################################################################

start_mongodb() {
    log_info "Checking MongoDB (Docker)..."
    
    # Check if MongoDB is accessible on port 27017
    if nc -z localhost 27017 2>/dev/null; then
        log_success "MongoDB available on port 27017 (Docker)"
        STARTED_SERVICES+=("mongodb")
        return 0
    else
        log_error "MongoDB not accessible on port 27017"
        log_warning "Please ensure MongoDB Docker container is running:"
        log_warning "  docker run -d -p 27017:27017 --name mongodb mongo"
        log_warning "Or start existing container:"
        log_warning "  docker start mongodb"
        cleanup_on_failure
    fi
}

start_redis() {
    log_info "Starting Redis..."
    
    if pgrep -x "redis-server" > /dev/null; then
        log_warning "Redis already running"
        STARTED_SERVICES+=("redis")
        return 0
    fi
    
    if command_exists redis-server; then
        redis-server --daemonize yes --logfile "$PROJECT_ROOT/logs/redis.log"
        if wait_for_port 6379 "Redis" 10; then
            log_success "Redis started"
            STARTED_SERVICES+=("redis")
            return 0
        else
            log_error "Redis started but not responding"
            cleanup_on_failure
        fi
    else
        log_error "Redis not found. Install with: brew install redis"
        cleanup_on_failure
    fi
}

start_ollama() {
    log_info "Starting Ollama..."
    
    if pgrep -x "ollama" > /dev/null; then
        log_warning "Ollama already running"
        
        # Verify it's actually responding
        if curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
            log_success "Ollama is healthy and responding"
            STARTED_SERVICES+=("ollama")
            return 0
        else
            log_warning "Ollama process exists but not responding, restarting..."
            pkill -9 ollama 2>/dev/null || true
            sleep 2
        fi
    fi
    
    if command_exists ollama; then
        ollama serve > "$PROJECT_ROOT/logs/ollama.log" 2>&1 &
        echo $! > "$PID_DIR/ollama.pid"
        
        # Wait for Ollama to be ready
        log_info "Waiting for Ollama to be ready..."
        local count=0
        while ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; do
            sleep 1
            count=$((count + 1))
            if [ $count -ge 15 ]; then
                log_error "Ollama failed to start within 15s"
                log_error "Check logs: tail -f logs/ollama.log"
                return 1
            fi
        done
        
        log_success "Ollama started and responding"
        STARTED_SERVICES+=("ollama")
        
        # Check and pull required models
        log_info "Checking required Ollama models..."
        local models_needed="gemma3:1b"
        local models_installed=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}')
        
        for model in $models_needed; do
            if echo "$models_installed" | grep -q "^$model"; then
                log_success "Model $model is available"
            else
                log_warning "Model $model not found, pulling..."
                if ollama pull "$model" 2>&1 | tee -a "$PROJECT_ROOT/logs/ollama.log"; then
                    log_success "Model $model pulled successfully"
                else
                    log_error "Failed to pull model $model"
                    log_warning "LangChain features may not work without this model"
                fi
            fi
        done
        
        return 0
    else
        log_error "Ollama not found. LangChain features will not work."
        log_error "Install from: https://ollama.ai"
        log_error "  macOS: brew install ollama"
        log_error "  Linux: curl -fsSL https://ollama.com/install.sh | sh"
        return 1
    fi
}


start_celery_worker() {
    log_info "Starting Celery Worker..."
    
    if [ -f "$PID_DIR/celery_worker.pid" ] && kill -0 $(cat "$PID_DIR/celery_worker.pid") 2>/dev/null; then
        log_warning "Celery Worker already running"
        return 0
    fi
    
    rm -f "$PID_DIR/celery_worker.pid"
    
    # Test Celery imports
    log_debug "Testing Celery imports..."
    if ! $PYTHON_CMD -c "from second_brain_database.tasks.celery_app import celery_app" 2>"$PROJECT_ROOT/logs/celery_import_test.log"; then
        log_error "Celery import test failed - missing dependencies"
        log_error "Check: cat logs/celery_import_test.log"
        tail -10 "$PROJECT_ROOT/logs/celery_import_test.log"
        cleanup_on_failure
    fi
    
    $PYTHON_CMD scripts/manual/start_celery_worker.py > "$PROJECT_ROOT/logs/celery_worker.log" 2>&1 &
    local pid=$!
    echo $pid > "$PID_DIR/celery_worker.pid"
    sleep 3
    
    if check_process_health "$PID_DIR/celery_worker.pid" "celery_worker"; then
        log_success "Celery Worker started (PID: $pid, queues: default, ai, voice, workflows)"
        STARTED_SERVICES+=("celery_worker")
        return 0
    else
        log_error "Celery Worker failed to start. Check logs: tail -f logs/celery_worker.log"
        log_info "Last 10 lines of log:"
        tail -10 "$PROJECT_ROOT/logs/celery_worker.log"
        cleanup_on_failure
    fi
}

start_celery_beat() {
    log_info "Starting Celery Beat..."
    
    if [ -f "$PID_DIR/celery_beat.pid" ] && kill -0 $(cat "$PID_DIR/celery_beat.pid") 2>/dev/null; then
        log_warning "Celery Beat already running"
        return 0
    fi
    
    rm -f "$PID_DIR/celery_beat.pid"
    
    $PYTHON_CMD scripts/manual/start_celery_beat.py > "$PROJECT_ROOT/logs/celery_beat.log" 2>&1 &
    local pid=$!
    echo $pid > "$PID_DIR/celery_beat.pid"
    sleep 3
    
    if check_process_health "$PID_DIR/celery_beat.pid" "celery_beat"; then
        log_success "Celery Beat started (PID: $pid)"
        STARTED_SERVICES+=("celery_beat")
        return 0
    else
        log_error "Celery Beat failed to start. Check logs: tail -f logs/celery_beat.log"
        log_info "Last 10 lines of log:"
        tail -10 "$PROJECT_ROOT/logs/celery_beat.log"
        cleanup_on_failure
    fi
}

start_flower() {
    log_info "Starting Flower Dashboard..."
    
    if [ -f "$PID_DIR/flower.pid" ] && kill -0 $(cat "$PID_DIR/flower.pid") 2>/dev/null; then
        log_warning "Flower already running"
        return 0
    fi
    
    rm -f "$PID_DIR/flower.pid"
    
    # Test flower import
    log_debug "Testing Flower imports..."
    if ! $PYTHON_CMD -c "import flower" 2>/dev/null; then
        log_warning "Flower not installed - skipping dashboard"
        log_info "Install with: uv pip install flower"
        return 0
    fi
    
    $PYTHON_CMD scripts/manual/start_flower.py > "$PROJECT_ROOT/logs/flower.log" 2>&1 &
    local pid=$!
    echo $pid > "$PID_DIR/flower.pid"
    
    if wait_for_port 5555 "Flower" 15; then
        log_success "Flower started on http://localhost:5555 (PID: $pid)"
        STARTED_SERVICES+=("flower")
        return 0
    else
        log_error "Flower failed to start. Check logs: tail -f logs/flower.log"
        log_info "Last 10 lines of log:"
        tail -10 "$PROJECT_ROOT/logs/flower.log"
        cleanup_on_failure
    fi
}

###############################################################################
# Main Startup Sequence
###############################################################################

main() {
    log_info "========================================"
    log_info "Second Brain Database - Startup"
    log_info "========================================"
    log_info "Startup log: $STARTUP_LOG"
    echo ""
    
    # Check uv and Python
    if ! command_exists uv; then
        log_error "uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    
    log_info "Python version: $($PYTHON_CMD --version 2>&1)"
    echo ""
    
    # Clean up any processes using our ports
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Pre-flight: Port Cleanup"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if ! cleanup_all_ports; then
        log_error "Failed to cleanup ports. Some services may be stuck."
        log_error "Try running ./stop.sh first or manually kill processes."
        exit 1
    fi
    echo ""
    
    # Start infrastructure services
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Phase 1: Infrastructure Services"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    start_mongodb
    start_redis
    start_ollama
    echo ""
    
    # Start application services
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Phase 2: Application Services"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    start_fastapi
    # start_chat_ui  # Disabled: start manually if needed with 'cd submodules/second-brain-database-chat/apps/web && pnpm dev'
    start_celery_beat
    start_flower
    echo ""
    
    # Summary
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_success "✓ All services started successfully!"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    log_info "${MAGENTA}Service URLs:${NC}"
    log_info "  - FastAPI:        http://localhost:8000"
    log_info "  - API Docs:       http://localhost:8000/docs"
    log_info "  - Flower:         http://localhost:5555"
    log_info "  - Ollama:         http://localhost:11434"
    echo ""
    log_info "${MAGENTA}Log Monitoring:${NC}"
    log_info "  - View single service:  ./scripts/startall/attach_service.sh [service]"
    log_info "  - New terminal window:  ./scripts/startall/open_service_terminal.sh [service]"
    log_info "  - All services (tabs):  ./scripts/startall/open_all_terminals.sh"
    log_info "  - Startup log:          tail -f $STARTUP_LOG"
    echo ""
    log_info "${MAGENTA}Quick Log Commands:${NC}"
    log_info "  - FastAPI errors:       tail -f logs/fastapi.log | grep ERROR"
    log_info "  - Celery tasks:         tail -f logs/celery_worker.log | grep 'Task.*succeeded'"
    log_info "  - All recent errors:    tail -f logs/*.log | grep -i error"
    echo ""
    log_info "${MAGENTA}Management:${NC}"
    log_info "  - Stop all services:    ./stop.sh"
    log_info "  - Check service status: ps aux | grep -E 'fastapi|celery|flower|ollama'"
    log_info "  - View PIDs:            ls -lh pids/"
    echo ""
}

# Run main
main
