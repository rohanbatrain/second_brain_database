#!/bin/bash
# Complete WebRTC Test Setup Script
# Sets up server, creates test users, and provides test instructions

set -e

echo "🚀 Starting Complete WebRTC Test Setup..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONFIG_PATH="/Users/rohan/Documents/repos/second_brain_database/.sbd"
SERVER_HOST="0.0.0.0"
SERVER_PORT="8000"
DOMAIN="dev-app-sbd.rohanbatra.in"

echo -e "${BLUE}📋 Configuration:${NC}"
echo "  Config file: $CONFIG_PATH"
echo "  Server: $SERVER_HOST:$SERVER_PORT"
echo "  Domain: $DOMAIN"
echo ""

# Check if config file exists
if [ ! -f "$CONFIG_PATH" ]; then
    echo -e "${RED}❌ Config file not found: $CONFIG_PATH${NC}"
    echo "Please ensure .sbd config file exists with proper settings."
    exit 1
fi

# Check if required services are running
echo -e "${BLUE}🔍 Checking required services...${NC}"

# Check MongoDB
if ! pgrep -f mongod > /dev/null; then
    echo -e "${YELLOW}⚠️  MongoDB not running. Starting...${NC}"
    brew services start mongodb/brew/mongodb-community
    sleep 3
fi

# Check Redis
if ! pgrep -f redis > /dev/null; then
    echo -e "${YELLOW}⚠️  Redis not running. Starting...${NC}"
    brew services start redis
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
cd /Users/rohan/Documents/repos/second_brain_database
python src/second_brain_database/main.py &
SERVER_PID=$!

# Wait for server to start
echo -e "${YELLOW}⏳ Waiting for server to start...${NC}"
sleep 5

# Check if server is responding
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Server started successfully on http://$SERVER_HOST:$SERVER_PORT${NC}"
else
    echo -e "${RED}❌ Server failed to start${NC}"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi

# Create test users
echo -e "${BLUE}👥 Creating WebRTC test users...${NC}"
./create_webrtc_test_users.sh

# Wait a moment for users to be created
sleep 2

# Get tokens
echo -e "${BLUE}🔑 Getting JWT tokens...${NC}"
./check_webrtc_users.sh

echo ""
echo -e "${GREEN}🎉 Setup Complete!${NC}"
echo ""
echo -e "${BLUE}📖 Test Instructions:${NC}"
echo ""
echo "1. 🌐 Open two browser windows/tabs"
echo ""
echo "2. 📱 In first window (User 1):"
echo "   Go to: https://$DOMAIN/webrtc_test.html"
echo "   Token should be pre-filled for webrtc_user1"
echo ""
echo "3. 📱 In second window (User 2):"
echo "   Go to: https://$DOMAIN/webrtc_test.html"
echo "   Token should be pre-filled for webrtc_user2"
echo ""
echo "4. 🎥 In both windows:"
echo "   - Select 'Cloudflare Tunnel' endpoint mode"
echo "   - Enter room name: 'test-room'"
echo "   - Click 'Connect to Room'"
echo "   - Grant camera/microphone permissions"
echo ""
echo "5. 📞 Start the call:"
echo "   - Click 'Start Call' in one of the windows"
echo "   - You should see video streams in both windows"
echo ""
echo -e "${YELLOW}💡 Troubleshooting:${NC}"
echo "   - If connection fails, check browser console for errors"
echo "   - Ensure Cloudflare tunnel is running: cloudflared tunnel list"
echo "   - Check server logs in terminal"
echo ""
echo -e "${BLUE}🛑 To stop the test:${NC}"
echo "   Press Ctrl+C to stop this script"
echo "   Server will be automatically stopped"
echo ""

# Wait for user input
echo -e "${GREEN}Press Enter when ready to start the test, or Ctrl+C to exit...${NC}"
read || true

# Cleanup on exit
cleanup() {
    echo ""
    echo -e "${BLUE}🧹 Cleaning up...${NC}"
    kill $SERVER_PID 2>/dev/null || true
    echo -e "${GREEN}✅ Test complete${NC}"
}

trap cleanup EXIT

# Keep server running
wait $SERVER_PID</content>
<parameter name="filePath">/Users/rohan/Documents/repos/second_brain_database/run_webrtc_test.sh