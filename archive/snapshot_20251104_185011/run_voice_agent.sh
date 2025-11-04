#!/bin/bash
# LiveKit Voice Agent Runner Script
# This script starts the LiveKit voice agent with proper environment setup

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT"

echo "Starting LiveKit Voice Agent..."
echo "Project root: $PROJECT_ROOT"
echo "Script directory: $SCRIPT_DIR"

# Check if Python virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment (.venv)..."
    source .venv/bin/activate
else
    echo "Warning: No virtual environment found. Using system Python."
fi

# Check if required environment variables are set
if [ -z "$LIVEKIT_API_KEY" ] || [ -z "$LIVEKIT_API_SECRET" ]; then
    echo "Error: LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set"
    echo "Please set these in your .env file or environment"
    exit 1
fi

if [ -z "$LIVEKIT_URL" ]; then
    echo "Error: LIVEKIT_URL must be set"
    echo "Please set this in your .env file or environment"
    exit 1
fi

if [ -z "$OLLAMA_HOST" ]; then
    echo "Error: OLLAMA_HOST must be set"
    echo "Please set this in your .env file or environment"
    exit 1
fi

# Run the voice agent
echo "Running voice agent..."
python scripts/manual/livekit_voice_agent.py

echo "Voice agent stopped."