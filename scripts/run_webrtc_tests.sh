#!/bin/bash

# WebRTC Complete Test Runner
# This script starts the server and runs comprehensive WebRTC tests

set -e

echo "🎥 WebRTC Test Runner - Complete Testing Suite"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONFIG_PATH="${HOME}/Documents/repos/second_brain_database/.sbd"
SERVER_HOST="127.0.0.1"
SERVER_PORT="8000"

echo -e "${BLUE}📋 Configuration:${NC}"
echo "  Config file: $CONFIG_PATH"
echo "  Server: $SERVER_HOST:$SERVER_PORT"
echo ""

# Check if config file exists
if [ ! -f "$CONFIG_PATH" ]; then
    echo -e "${RED}❌ Config file not found: $CONFIG_PATH${NC}"
    echo "Please ensure .sbd config file exists with proper settings."
    exit 1
fi

# Check Python environment
echo -e "${BLUE}🐍 Checking Python environment...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 not found${NC}"
    exit 1
fi

# Check required services
echo -e "${BLUE}🔍 Checking required services...${NC}"

# Check MongoDB
if ! pgrep -f mongod > /dev/null; then
    echo -e "${YELLOW}⚠️  MongoDB not running. Starting...${NC}"
    if command -v brew &> /dev/null; then
        brew services start mongodb/brew/mongodb-community
    else
        echo -e "${RED}❌ Please start MongoDB manually${NC}"
        exit 1
    fi
    sleep 3
fi

# Check Redis
if ! pgrep -f redis > /dev/null; then
    echo -e "${YELLOW}⚠️  Redis not running. Starting...${NC}"
    if command -v brew &> /dev/null; then
        brew services start redis
    else
        echo -e "${RED}❌ Please start Redis manually${NC}"
        exit 1
    fi
    sleep 2
fi

echo -e "${GREEN}✅ Services ready${NC}"

# Kill any existing server
echo -e "${BLUE}🛑 Stopping any existing server...${NC}"
pkill -f "python.*main.py" || true
sleep 2

# Start the server
echo -e "${BLUE}🚀 Starting Second Brain Database server...${NC}"
export SECOND_BRAIN_DATABASE_CONFIG_PATH="$CONFIG_PATH"

cd "$(dirname "$0")"

python3 src/second_brain_database/main.py &
SERVER_PID=$!

# Wait for server to start
echo -e "${YELLOW}⏳ Waiting for server to start...${NC}"
sleep 8

# Check if server is responding
MAX_RETRIES=10
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:$SERVER_PORT/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Server started successfully${NC}"
        break
    else
        echo -e "${YELLOW}⏳ Server not ready yet, retrying... ($((RETRY_COUNT + 1))/$MAX_RETRIES)${NC}"
        sleep 3
        RETRY_COUNT=$((RETRY_COUNT + 1))
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}❌ Server failed to start after $MAX_RETRIES attempts${NC}"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi

# Show server info
echo -e "${BLUE}📊 Server Information:${NC}"
HEALTH_RESPONSE=$(curl -s http://localhost:$SERVER_PORT/health 2>/dev/null || echo '{"status": "unknown"}')
echo "  Health Check: $HEALTH_RESPONSE"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo -e "${BLUE}🧹 Cleaning up...${NC}"
    
    # Kill server
    if [ ! -z "$SERVER_PID" ]; then
        echo "  Stopping server (PID: $SERVER_PID)..."
        kill $SERVER_PID 2>/dev/null || true
        sleep 2
    fi
    
    echo -e "${GREEN}✅ Cleanup complete${NC}"
}

trap cleanup EXIT

# Run the tests
echo -e "${BLUE}🧪 Running WebRTC Tests...${NC}"
echo ""

# Test selection menu
echo "Select test to run:"
echo "1) Complete WebRTC Test Suite (comprehensive)"
echo "2) Simple Two-Token Test (quick)"
echo "3) Both tests (recommended)"
echo ""

read -p "Enter choice [1-3]: " TEST_CHOICE

case $TEST_CHOICE in
    1)
        echo -e "${BLUE}Running Complete Test Suite...${NC}"
        python3 test_webrtc_complete.py
        TEST_RESULT=$?
        ;;
    2)
        echo -e "${BLUE}Running Simple Two-Token Test...${NC}"
        python3 test_webrtc_simple.py
        TEST_RESULT=$?
        ;;
    3)
        echo -e "${BLUE}Running Both Tests...${NC}"
        echo ""
        echo -e "${YELLOW}▶️  Starting Simple Test...${NC}"
        python3 test_webrtc_simple.py
        SIMPLE_RESULT=$?
        
        echo ""
        echo -e "${YELLOW}▶️  Starting Complete Test...${NC}"
        python3 test_webrtc_complete.py
        COMPLETE_RESULT=$?
        
        # Overall result
        if [ $SIMPLE_RESULT -eq 0 ] && [ $COMPLETE_RESULT -eq 0 ]; then
            TEST_RESULT=0
        else
            TEST_RESULT=1
        fi
        
        echo ""
        echo -e "${BLUE}📊 Test Summary:${NC}"
        if [ $SIMPLE_RESULT -eq 0 ]; then
            echo -e "  Simple Test: ${GREEN}✅ PASSED${NC}"
        else
            echo -e "  Simple Test: ${RED}❌ FAILED${NC}"
        fi
        
        if [ $COMPLETE_RESULT -eq 0 ]; then
            echo -e "  Complete Test: ${GREEN}✅ PASSED${NC}"
        else
            echo -e "  Complete Test: ${RED}❌ FAILED${NC}"
        fi
        ;;
    *)
        echo -e "${RED}❌ Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}🎯 Final Results:${NC}"

if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
    echo ""
    echo -e "${GREEN}✅ WebRTC implementation is working correctly${NC}"
    echo -e "${GREEN}✅ JWT token authentication works${NC}"
    echo -e "${GREEN}✅ Two-token signaling is functional${NC}"
    echo ""
    echo -e "${BLUE}💡 Your WebRTC system is ready for production!${NC}"
else
    echo -e "${RED}❌ TESTS FAILED${NC}"
    echo ""
    echo -e "${RED}🔍 Issues found with WebRTC implementation${NC}"
    echo -e "${YELLOW}📋 Check the test output above for details${NC}"
    echo ""
    echo -e "${BLUE}🛠️  Common issues to check:${NC}"
    echo "   1. JWT token generation and validation"
    echo "   2. WebSocket authentication middleware"
    echo "   3. Redis Pub/Sub configuration"
    echo "   4. WebRTC signaling message routing"
fi

exit $TEST_RESULT