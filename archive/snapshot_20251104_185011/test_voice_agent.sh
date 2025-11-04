#!/bin/bash
# Voice Agent Testing Setup Script
# This script helps set up and test the voice agent with MCP integration

set -e

echo "🎤 Second Brain Database - Voice Agent Setup"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    print_success "Docker is running"
}

# Check if required files exist
check_files() {
    local files=(".sbd" "docker-compose.yml" "config/livekit-config.yaml")
    for file in "${files[@]}"; do
        if [ ! -f "$file" ]; then
            print_error "Required file missing: $file"
            exit 1
        fi
    done
    print_success "All required configuration files found"
}

# Start Docker services
start_services() {
    print_status "Starting Docker services (this may take a few minutes)..."

    # Start core services first
    docker-compose up -d mongo redis ollama-cpu
    print_status "Waiting for core services to be ready..."
    sleep 10

    # Start LiveKit server
    docker-compose up -d livekit
    print_status "Waiting for LiveKit server to be ready..."
    sleep 5

    print_success "Docker services started"
}

# Check service health
check_services() {
    print_status "Checking service health..."

    # Check MongoDB
    if docker-compose exec -T mongo mongo --eval "db.stats()" > /dev/null 2>&1; then
        print_success "MongoDB is healthy"
    else
        print_warning "MongoDB health check failed"
    fi

    # Check Redis
    if docker-compose exec -T redis redis-cli ping | grep -q PONG; then
        print_success "Redis is healthy"
    else
        print_warning "Redis health check failed"
    fi

    # Check Ollama
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        print_success "Ollama is responding"
    else
        print_warning "Ollama is not responding (this is normal if models aren't pulled yet)"
    fi

    # Check LiveKit
    if curl -s http://localhost:7881/health > /dev/null 2>&1; then
        print_success "LiveKit server is healthy"
    else
        print_warning "LiveKit server health check failed"
    fi
}

# Start FastAPI server
start_backend() {
    print_status "Starting FastAPI backend server..."

    # Check if Python virtual environment exists
    if [ ! -d ".venv" ]; then
        print_warning "Virtual environment not found. Installing dependencies..."
        uv sync
    fi

    # Start the server in background
    nohup python scripts/manual/start_fastapi_server.py > backend.log 2>&1 &
    echo $! > backend.pid

    print_status "Waiting for backend to start..."
    sleep 5

    # Check if backend is responding
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        print_success "FastAPI backend is running on http://localhost:8000"
    else
        print_error "FastAPI backend failed to start. Check backend.log for details."
        exit 1
    fi
}

# Run text-based tests
run_text_tests() {
    print_status "Running text-based MCP integration tests..."

    if python test_voice_agent_mcp.py; then
        print_success "Text-based MCP tests passed!"
    else
        print_error "Text-based MCP tests failed"
        exit 1
    fi
}

# Open web interface
open_web_interface() {
    print_status "Opening web-based testing interface..."

    if command -v python3 &> /dev/null; then
        python3 -c "
import webbrowser
import os
html_path = os.path.abspath('voice_agent_test.html')
print('Opening voice agent test interface in browser...')
webbrowser.open(f'file://{html_path}')
print('Browser opened. Make sure your FastAPI backend is running on http://localhost:8000')
"
    else
        print_warning "Python3 not found. Please manually open voice_agent_test.html in your browser"
    fi
}

# Show usage information
show_usage() {
    echo
    echo "Voice Agent Testing Options:"
    echo "==========================="
    echo
    echo "1. Text-Based Testing (Recommended for development):"
    echo "   - Tests MCP tool integration without LiveKit"
    echo "   - Faster setup, no audio requirements"
    echo "   - Command: $0 text"
    echo
    echo "2. Full Voice Testing:"
    echo "   - Real-time voice with LiveKit server"
    echo "   - Requires microphone/speakers"
    echo "   - Command: $0 voice"
    echo
    echo "3. Web Interface:"
    echo "   - Interactive testing in browser"
    echo "   - Command: $0 web"
    echo
    echo "4. Setup Only:"
    echo "   - Start services without running tests"
    echo "   - Command: $0 setup"
    echo
    echo "5. Cleanup:"
    echo "   - Stop all services and clean up"
    echo "   - Command: $0 cleanup"
    echo
}

# Cleanup function
cleanup() {
    print_status "Cleaning up..."

    # Stop background processes
    if [ -f "backend.pid" ]; then
        kill $(cat backend.pid) 2>/dev/null || true
        rm -f backend.pid
    fi

    # Stop Docker services
    docker-compose down

    print_success "Cleanup complete"
}

# Main script logic
main() {
    local command=${1:-"help"}

    case $command in
        "setup")
            print_status "Setting up voice agent testing environment..."
            check_docker
            check_files
            start_services
            check_services
            start_backend
            print_success "Setup complete! Run '$0 text' or '$0 web' to test."
            ;;

        "text")
            print_status "Running text-based MCP integration tests..."
            run_text_tests
            ;;

        "voice")
            print_status "Setting up for full voice testing..."
            check_docker
            check_files
            start_services
            check_services
            start_backend
            print_success "Voice testing environment ready!"
            print_status "To start a voice agent session:"
            echo "  python scripts/launch_voice_agent.py --room test-room"
            ;;

        "web")
            print_status "Opening web-based testing interface..."
            open_web_interface
            ;;

        "cleanup")
            cleanup
            ;;

        "help"|*)
            show_usage
            ;;
    esac
}

# Run main function with all arguments
main "$@"