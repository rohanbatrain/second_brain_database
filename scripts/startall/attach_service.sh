#!/usr/bin/env bash

###############################################################################
# Second Brain Database - Attach to Service Logs
#
# Opens service logs in real-time in current terminal
# Usage: ./attach_service.sh [service_name]
###############################################################################

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/../.."
LOGS_DIR="$PROJECT_ROOT/logs"

# Available services
SERVICES=(
    "mongodb"
    "redis"
    "ollama"
    "livekit"
    "fastapi"
    "voice_worker"
    "celery_worker"
    "celery_beat"
    "flower"
)

show_menu() {
    echo -e "${BLUE}Available Services:${NC}"
    echo ""
    for i in "${!SERVICES[@]}"; do
        service="${SERVICES[$i]}"
        log_file="$LOGS_DIR/${service}.log"
        
        if [ -f "$log_file" ]; then
            status="${GREEN}●${NC}"
            size=$(du -h "$log_file" | cut -f1)
        else
            status="${RED}○${NC}"
            size="N/A"
        fi
        
        printf "  %s %2d) %-20s (Size: %s)\n" "$status" "$((i+1))" "$service" "$size"
    done
    echo ""
    echo -e "${YELLOW}Usage: ./attach_service.sh [number|name]${NC}"
    echo -e "${YELLOW}Example: ./attach_service.sh fastapi${NC}"
    echo -e "${YELLOW}Example: ./attach_service.sh 5${NC}"
    echo ""
}

attach_to_service() {
    local service="$1"
    
    # Special handling for MongoDB (runs via Docker)
    if [ "$service" = "mongodb" ]; then
        echo -e "${YELLOW}MongoDB runs via Docker on port 27017${NC}"
        echo -e "${YELLOW}To view MongoDB logs, use:${NC}"
        echo -e "  ${GREEN}docker logs -f <mongodb_container_name>${NC}"
        echo ""
        echo -e "${BLUE}Checking MongoDB connection...${NC}"
        if nc -z localhost 27017 2>/dev/null; then
            echo -e "${GREEN}✓ MongoDB is accessible on port 27017${NC}"
        else
            echo -e "${RED}✗ MongoDB is not accessible on port 27017${NC}"
        fi
        exit 0
    fi
    
    local log_file="$LOGS_DIR/${service}.log"
    
    if [ ! -f "$log_file" ]; then
        echo -e "${RED}Error: Log file not found: $log_file${NC}"
        echo -e "${YELLOW}Service may not be running yet${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Attaching to $service logs...${NC}"
    echo -e "${YELLOW}Press Ctrl+C to detach${NC}"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Follow log file
    tail -f "$log_file"
}

# Main logic
if [ $# -eq 0 ]; then
    show_menu
    exit 0
fi

SERVICE_INPUT="$1"

# Check if input is a number
if [[ "$SERVICE_INPUT" =~ ^[0-9]+$ ]]; then
    INDEX=$((SERVICE_INPUT - 1))
    if [ $INDEX -ge 0 ] && [ $INDEX -lt ${#SERVICES[@]} ]; then
        SERVICE_NAME="${SERVICES[$INDEX]}"
    else
        echo -e "${RED}Error: Invalid service number${NC}"
        show_menu
        exit 1
    fi
else
    SERVICE_NAME="$SERVICE_INPUT"
fi

# Validate service name
if [[ ! " ${SERVICES[@]} " =~ " ${SERVICE_NAME} " ]]; then
    echo -e "${RED}Error: Unknown service: $SERVICE_NAME${NC}"
    show_menu
    exit 1
fi

attach_to_service "$SERVICE_NAME"
