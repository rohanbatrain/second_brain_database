#!/usr/bin/env bash

###############################################################################
# Second Brain Database - Open All Services in Separate Terminals
#
# Opens a new Terminal window for each service
###############################################################################

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Services to open
SERVICES=(
    "fastapi"
    "celery_worker"
    "celery_beat"
    "flower"
    "voice_worker"
    "livekit"
    "ollama"
)

echo "Opening terminals for all services..."

for service in "${SERVICES[@]}"; do
    ./open_service_terminal.sh "$service"
    sleep 0.5  # Small delay between windows
done

echo "All service terminals opened!"
