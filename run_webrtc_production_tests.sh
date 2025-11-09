#!/bin/bash

# WebRTC Production Test Runner
# Enhanced version with comprehensive service management and validation

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_URL="http://localhost:8000"
SERVER_PID_FILE="$SCRIPT_DIR/.server.pid"
LOG_DIR="$SCRIPT_DIR/logs"
TEST_LOG="$LOG_DIR/webrtc_test_$(date +%Y%m%d_%H%M%S).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$TEST_LOG"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$TEST_LOG"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$TEST_LOG"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$TEST_LOG"
}

# Create log directory
mkdir -p "$LOG_DIR"

log_info "WebRTC Production Test Runner Started"
log_info "Test log: $TEST_LOG"

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if we're in the right directory
    if [[ ! -f "pyproject.toml" ]]; then
        log_error "Not in the correct directory. Please run from the project root."
        exit 1
    fi
    
    # Check Python environment
    if ! command -v python &> /dev/null; then
        log_error "Python not found. Please ensure Python is installed and activated."
        exit 1
    fi
    
    # Check required Python packages
    if ! python -c "import fastapi, httpx, websockets" &> /dev/null; then
        log_error "Required packages not found. Please install dependencies: pip install fastapi httpx websockets"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Enhanced service management
check_service() {
    local service_name=$1
    local port=$2
    local max_attempts=${3:-30}
    local attempt=0
    
    log_info "Checking $service_name on port $port..."
    
    while [[ $attempt -lt $max_attempts ]]; do
        if nc -z localhost "$port" 2>/dev/null; then
            log_success "$service_name is running on port $port"
            return 0
        fi
        
        ((attempt++))
        if [[ $attempt -eq 1 ]]; then
            log_info "Waiting for $service_name to start..."
        fi
        
        sleep 1
    done
    
    log_error "$service_name failed to start on port $port after $max_attempts seconds"
    return 1
}

start_mongodb() {
    log_info "Starting MongoDB..."
    
    # Check if MongoDB is already running
    if check_service "MongoDB" 27017 3; then
        return 0
    fi
    
    # Try to start MongoDB using different methods
    if command -v brew &> /dev/null && brew services list | grep mongodb-community &> /dev/null; then
        log_info "Starting MongoDB via Homebrew..."
        brew services start mongodb-community || true
    elif command -v mongod &> /dev/null; then
        log_info "Starting MongoDB directly..."
        mongod --fork --logpath "$LOG_DIR/mongodb.log" --dbpath ./data/db || true
    elif command -v systemctl &> /dev/null; then
        log_info "Starting MongoDB via systemctl..."
        sudo systemctl start mongod || true
    else
        log_warning "MongoDB not found or cannot be started automatically"
        log_info "Please start MongoDB manually and ensure it's running on port 27017"
        read -p "Press Enter when MongoDB is ready..."
    fi
    
    # Verify MongoDB is running
    check_service "MongoDB" 27017 30
}

start_redis() {
    log_info "Starting Redis..."
    
    # Check if Redis is already running
    if check_service "Redis" 6379 3; then
        return 0
    fi
    
    # Try to start Redis using different methods
    if command -v brew &> /dev/null && brew services list | grep redis &> /dev/null; then
        log_info "Starting Redis via Homebrew..."
        brew services start redis || true
    elif command -v redis-server &> /dev/null; then
        log_info "Starting Redis directly..."
        redis-server --daemonize yes --logfile "$LOG_DIR/redis.log" || true
    elif command -v systemctl &> /dev/null; then
        log_info "Starting Redis via systemctl..."
        sudo systemctl start redis || true
    else
        log_warning "Redis not found or cannot be started automatically"
        log_info "Please start Redis manually and ensure it's running on port 6379"
        read -p "Press Enter when Redis is ready..."
    fi
    
    # Verify Redis is running
    check_service "Redis" 6379 30
}

start_server() {
    log_info "Starting FastAPI server..."
    
    # Check if server is already running
    if check_service "FastAPI Server" 8000 3; then
        log_warning "Server already running on port 8000"
        return 0
    fi
    
    # Start the server in background
    log_info "Launching server in background..."
    python -m uvicorn src.second_brain_database.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --log-level info \
        >> "$LOG_DIR/server.log" 2>&1 &
    
    SERVER_PID=$!
    echo $SERVER_PID > "$SERVER_PID_FILE"
    
    log_info "Server started with PID: $SERVER_PID"
    
    # Wait for server to be ready
    if check_service "FastAPI Server" 8000 60; then
        # Additional health check
        local attempt=0
        while [[ $attempt -lt 30 ]]; do
            if curl -s "$BASE_URL/health" > /dev/null 2>&1; then
                log_success "Server health check passed"
                return 0
            fi
            ((attempt++))
            sleep 1
        done
        
        log_error "Server health check failed"
        return 1
    else
        return 1
    fi
}

stop_server() {
    if [[ -f "$SERVER_PID_FILE" ]]; then
        local pid=$(cat "$SERVER_PID_FILE")
        log_info "Stopping server (PID: $pid)..."
        
        if kill "$pid" 2>/dev/null; then
            # Wait for graceful shutdown
            local attempt=0
            while [[ $attempt -lt 10 ]] && kill -0 "$pid" 2>/dev/null; do
                sleep 1
                ((attempt++))
            done
            
            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                log_warning "Force killing server..."
                kill -9 "$pid" 2>/dev/null || true
            fi
            
            log_success "Server stopped"
        else
            log_warning "Server was not running or already stopped"
        fi
        
        rm -f "$SERVER_PID_FILE"
    fi
}

run_test() {
    local test_type=$1
    local test_file=""
    local test_description=""
    
    case $test_type in
        "simple")
            test_file="test_webrtc_simple.py"
            test_description="Simple 2-Token WebRTC Test"
            ;;
        "production")
            test_file="test_webrtc_production.py"
            test_description="Production-Ready WebRTC Test Suite"
            ;;
        "complete")
            test_file="test_webrtc_complete.py"
            test_description="Complete WebRTC Test Suite"
            ;;
        "manual")
            test_file="test_webrtc_manual.py"
            test_description="Manual WebRTC Endpoint Test"
            ;;
        *)
            log_error "Unknown test type: $test_type"
            return 1
            ;;
    esac
    
    log_info "Running $test_description..."
    log_info "Test file: $test_file"
    
    if [[ ! -f "$test_file" ]]; then
        log_error "Test file not found: $test_file"
        return 1
    fi
    
    # Run the test and capture both stdout and return code
    local test_start=$(date +%s)
    
    if python "$test_file" 2>&1 | tee -a "$TEST_LOG"; then
        local test_end=$(date +%s)
        local test_duration=$((test_end - test_start))
        log_success "$test_description completed successfully in ${test_duration}s"
        return 0
    else
        local test_end=$(date +%s)
        local test_duration=$((test_end - test_start))
        log_error "$test_description failed after ${test_duration}s"
        return 1
    fi
}

cleanup() {
    log_info "Cleaning up..."
    stop_server
    
    # Clean up any orphaned processes
    pkill -f "uvicorn.*second_brain_database" || true
    
    log_success "Cleanup completed"
}

# Set up signal handlers
trap cleanup EXIT
trap 'log_warning "Test interrupted by user"; exit 130' INT TERM

# Main execution
main() {
    local test_type=""
    local auto_mode=false
    local start_services=true
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --test|-t)
                test_type="$2"
                shift 2
                ;;
            --auto|-a)
                auto_mode=true
                shift
                ;;
            --no-services)
                start_services=false
                shift
                ;;
            --help|-h)
                echo "WebRTC Production Test Runner"
                echo ""
                echo "Usage: $0 [options]"
                echo ""
                echo "Options:"
                echo "  -t, --test TYPE     Run specific test (simple|production|complete|manual)"
                echo "  -a, --auto          Run in automated mode (no user interaction)"
                echo "  --no-services       Don't start/stop services (assume they're running)"
                echo "  -h, --help          Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0                           # Interactive mode with service management"
                echo "  $0 --test production         # Run production test with service management"
                echo "  $0 --test simple --no-services  # Run simple test assuming services are running"
                echo "  $0 --auto --test production  # Automated production test"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    log_info "Starting WebRTC Production Test Runner"
    log_info "Mode: $([ "$auto_mode" = true ] && echo "Automated" || echo "Interactive")"
    log_info "Service management: $([ "$start_services" = true ] && echo "Enabled" || echo "Disabled")"
    
    # Check prerequisites
    check_prerequisites
    
    # Start services if requested
    if [[ "$start_services" = true ]]; then
        log_info "Starting required services..."
        
        if ! start_mongodb; then
            log_error "Failed to start MongoDB"
            exit 1
        fi
        
        if ! start_redis; then
            log_error "Failed to start Redis"  
            exit 1
        fi
        
        if ! start_server; then
            log_error "Failed to start FastAPI server"
            exit 1
        fi
        
        log_success "All services started successfully"
    else
        log_info "Skipping service startup (assuming services are running)"
        
        # Verify services are available
        check_service "MongoDB" 27017 3 || log_warning "MongoDB may not be running"
        check_service "Redis" 6379 3 || log_warning "Redis may not be running"
        check_service "FastAPI Server" 8000 3 || { log_error "FastAPI server not running"; exit 1; }
    fi
    
    # Determine test to run
    if [[ -z "$test_type" ]] && [[ "$auto_mode" = false ]]; then
        echo ""
        echo "🧪 Available WebRTC Tests:"
        echo "1) Simple 2-Token Test (Quick validation)"
        echo "2) Production Test Suite (Comprehensive validation)"
        echo "3) Complete Test Suite (Original comprehensive test)"
        echo "4) Manual Endpoint Test (Basic API validation)"
        echo "5) Run All Tests"
        echo ""
        read -p "Select test to run (1-5): " choice
        
        case $choice in
            1) test_type="simple" ;;
            2) test_type="production" ;;
            3) test_type="complete" ;;
            4) test_type="manual" ;;
            5) test_type="all" ;;
            *) 
                log_error "Invalid choice: $choice"
                exit 1
                ;;
        esac
    elif [[ -z "$test_type" ]]; then
        # Default to production test in auto mode
        test_type="production"
    fi
    
    # Run tests
    local overall_result=0
    
    if [[ "$test_type" = "all" ]]; then
        log_info "Running all WebRTC tests..."
        
        local tests=("manual" "simple" "production")
        local passed=0
        local total=${#tests[@]}
        
        for test in "${tests[@]}"; do
            echo ""
            log_info "=" "Running $test test..." "="
            
            if run_test "$test"; then
                ((passed++))
            else
                overall_result=1
            fi
            
            # Small delay between tests
            sleep 2
        done
        
        echo ""
        log_info "=" "ALL TESTS SUMMARY" "="
        log_info "Passed: $passed/$total tests"
        
        if [[ $passed -eq $total ]]; then
            log_success "🎉 All WebRTC tests passed!"
        else
            log_error "❌ Some WebRTC tests failed"
            overall_result=1
        fi
        
    else
        if ! run_test "$test_type"; then
            overall_result=1
        fi
    fi
    
    # Final summary
    echo ""
    log_info "Test execution completed"
    log_info "Log file: $TEST_LOG"
    
    if [[ $overall_result -eq 0 ]]; then
        log_success "🎉 WebRTC testing completed successfully!"
        echo ""
        echo "✅ Your WebRTC implementation is working correctly!"
        echo "🚀 Ready for production use with dual-token authentication."
    else
        log_error "❌ WebRTC testing completed with failures"
        echo ""
        echo "🔍 Check the test logs for detailed error information:"
        echo "   $TEST_LOG"
        echo ""
        echo "💡 Common fixes:"
        echo "   - Ensure MongoDB and Redis are running"
        echo "   - Check server logs in $LOG_DIR/server.log"
        echo "   - Verify network connectivity and ports"
    fi
    
    exit $overall_result
}

# Run main function
main "$@"