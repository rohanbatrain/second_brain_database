#!/usr/bin/env bash
"""
Production Streamlit RAG App Launcher

This script sets up and launches the Streamlit RAG application with proper
configuration for production use.

Usage:
    ./start_streamlit_app.sh [port] [host]
    
Examples:
    ./start_streamlit_app.sh                    # Default: localhost:8501
    ./start_streamlit_app.sh 8502              # Custom port
    ./start_streamlit_app.sh 8502 0.0.0.0      # Custom port and host
"""

# Default configuration
DEFAULT_PORT=8501
DEFAULT_HOST="localhost"
API_BASE_URL="http://localhost:8000"

# Parse arguments
PORT=${1:-$DEFAULT_PORT}
HOST=${2:-$DEFAULT_HOST}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Second Brain RAG Streamlit App${NC}"
echo -e "${YELLOW}📍 Host: ${HOST}${NC}"
echo -e "${YELLOW}🔌 Port: ${PORT}${NC}"
echo -e "${YELLOW}🌐 API Base URL: ${API_BASE_URL}${NC}"

# Check if the main API is running
echo -e "\n${BLUE}🔍 Checking API connectivity...${NC}"
if curl -s -o /dev/null -w "%{http_code}" "${API_BASE_URL}/health" | grep -q "200\|404"; then
    echo -e "${GREEN}✅ API is accessible${NC}"
else
    echo -e "${RED}❌ Warning: API at ${API_BASE_URL} is not accessible${NC}"
    echo -e "${YELLOW}⚠️  Make sure your Second Brain Database API is running${NC}"
fi

# Check Python dependencies
echo -e "\n${BLUE}🔍 Checking Python dependencies...${NC}"
if python -c "import streamlit, requests, pandas" 2>/dev/null; then
    echo -e "${GREEN}✅ Core dependencies available${NC}"
else
    echo -e "${RED}❌ Missing dependencies. Installing...${NC}"
    pip install -r streamlit_requirements.txt
fi

# Create Streamlit config directory if it doesn't exist
mkdir -p ~/.streamlit

# Create Streamlit configuration
cat > ~/.streamlit/config.toml << EOF
[server]
port = ${PORT}
address = "${HOST}"
headless = true
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false
serverAddress = "${HOST}"
serverPort = ${PORT}

[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"

[logger]
level = "info"
messageFormat = "%(asctime)s %(message)s"
EOF

echo -e "${GREEN}📝 Streamlit configuration created${NC}"

# Export environment variables for the app
export API_BASE_URL="${API_BASE_URL}"
export STREAMLIT_PORT="${PORT}"
export STREAMLIT_HOST="${HOST}"

echo -e "\n${GREEN}🎯 Launching Streamlit application...${NC}"
echo -e "${BLUE}📱 Application will be available at: http://${HOST}:${PORT}${NC}"
echo -e "${YELLOW}⏹️  Press Ctrl+C to stop the application${NC}\n"

# Launch Streamlit with the configuration
uv run streamlit run streamlit_rag_app.py \
    --server.port="${PORT}" \
    --server.address="${HOST}" \
    --server.headless=true \
    --browser.gatherUsageStats=false