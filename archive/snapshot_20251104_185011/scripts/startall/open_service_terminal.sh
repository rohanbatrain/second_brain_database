#!/usr/bin/env bash

###############################################################################
# Second Brain Database - Open Service in New Terminal
#
# Opens a new macOS Terminal window following service logs
# Usage: ./open_service_terminal.sh [service_name]
###############################################################################

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/../.."

if [ $# -eq 0 ]; then
    echo "Usage: ./open_service_terminal.sh [service_name]"
    echo ""
    echo "Available services:"
    echo "  mongodb, redis, ollama, livekit"
    echo "  fastapi, voice_worker, celery_worker, celery_beat, flower"
    echo ""
    echo "Example: ./open_service_terminal.sh fastapi"
    exit 1
fi

SERVICE_NAME="$1"

# Open new Terminal window with the service log
osascript <<EOF
tell application "Terminal"
    do script "cd '$PROJECT_ROOT' && scripts/startall/attach_service.sh $SERVICE_NAME"
    activate
end tell
EOF
