#!/bin/bash

# Enable strict mode for better error handling
set -euo pipefail
IFS=$'\n\t'

# Function to validate non-empty input
validate_input() {
    if [ -z "$1" ]; then
        echo "Error: $2 cannot be empty. Exiting." >&2
        exit 1
    fi
}

# Function to validate numeric input
validate_numeric_input() {
    if ! [[ "$1" =~ ^[0-9]+$ ]]; then
        echo "Error: $2 must be a valid number. Exiting." >&2
        exit 1
    fi
}

# Function to log messages
log() {
    echo "[INFO] $1"
}

# Prompt user for environment choice first
log "Prompting for environment choice..."
echo "Choose the environment to run the application:"
echo "1. Docker"
echo "2. Bare Metal"
read -p "Enter your choice (1 or 2): " choice

if [[ "$choice" != "1" && "$choice" != "2" ]]; then
    echo "Invalid choice. Exiting." >&2
    exit 1
fi

# Adjust default values based on the environment
if [ "$choice" -eq 1 ]; then
    log "Configuring for Docker environment..."
    MONGO_URL="mongodb://mongo:27017"
    REDIS_HOST="redis"
    REDIS_STORAGE_URI="redis://redis:6379/0"
else
    log "Configuring for Bare Metal environment..."
    MONGO_URL="mongodb://127.0.0.1:27017"
    REDIS_HOST="127.0.0.1"
    REDIS_STORAGE_URI="redis://127.0.0.1:6379/0"
fi

# Check if environment variables are already defined
log "Checking for existing environment variables..."
if [ -n "${MONGO_URL:-}" ] || [ -n "${MONGO_DB_NAME:-}" ] || [ -n "${SECRET_KEY:-}" ] || [ -n "${JWT_EXPIRY:-}" ] || [ -n "${JWT_REFRESH_EXPIRY:-}" ] || [ -n "${MT_API:-}" ] || [ -n "${REDIS_HOST:-}" ] || [ -n "${REDIS_PORT:-}" ] || [ -n "${REDIS_DB:-}" ] || [ -n "${REDIS_STORAGE_URI:-}" ] || [ -n "${MAIL_DEFAULT_SENDER:-}" ] || [ -n "${MAIL_SENDER_NAME:-}" ]; then
    log "Some environment variables are already defined."
    read -p "Do you want to load values from the environment? (y/n): " load_from_env
    if [[ "$load_from_env" == "y" || "$load_from_env" == "Y" ]]; then
        log "Loading values from the environment..."
        MONGO_URL=${MONGO_URL:-""}
        MONGO_DB_NAME=${MONGO_DB_NAME:-""}
        SECRET_KEY=${SECRET_KEY:-""}
        JWT_EXPIRY=${JWT_EXPIRY:-""}
        JWT_REFRESH_EXPIRY=${JWT_REFRESH_EXPIRY:-""}
        MT_API=${MT_API:-""}
        REDIS_HOST=${REDIS_HOST:-""}
        REDIS_PORT=${REDIS_PORT:-""}
        REDIS_DB=${REDIS_DB:-""}
        REDIS_STORAGE_URI=${REDIS_STORAGE_URI:-""}
        MAIL_DEFAULT_SENDER=${MAIL_DEFAULT_SENDER:-""}
        MAIL_SENDER_NAME=${MAIL_SENDER_NAME:-""}
    else
        log "Proceeding with manual input..."
    fi
fi

# Prompt user for undefined configuration values with defaults
if [ -z "${MONGO_URL:-}" ]; then
    read -p "Enter MongoDB URL [Default: mongodb://127.0.0.1:27017]: " MONGO_URL
    MONGO_URL=${MONGO_URL:-"mongodb://127.0.0.1:27017"}
    validate_input "$MONGO_URL" "MongoDB URL"
fi
if [ -z "${MONGO_DB_NAME:-}" ]; then
    read -p "Enter MongoDB Database Name [Default: Second_Brain_Database]: " MONGO_DB_NAME
    MONGO_DB_NAME=${MONGO_DB_NAME:-"Second_Brain_Database"}
    validate_input "$MONGO_DB_NAME" "MongoDB Database Name"
fi
if [ -z "${SECRET_KEY:-}" ]; then
    read -p "Enter Secret Key (at least 32 characters) [Default: auto-generated]: " SECRET_KEY
    SECRET_KEY=${SECRET_KEY:-$(openssl rand -base64 32)}
    validate_input "$SECRET_KEY" "Secret Key"
    if [ ${#SECRET_KEY} -lt 32 ]; then
        echo "Error: Secret Key must be at least 32 characters. Exiting." >&2
        exit 1
    fi
fi
if [ -z "${JWT_EXPIRY:-}" ]; then
    read -p "Enter JWT Expiry (e.g., 1h) [Default: 1h]: " JWT_EXPIRY
    JWT_EXPIRY=${JWT_EXPIRY:-"1h"}
    validate_input "$JWT_EXPIRY" "JWT Expiry"
fi
if [ -z "${JWT_REFRESH_EXPIRY:-}" ]; then
    read -p "Enter JWT Refresh Expiry (e.g., 7d) [Default: 7d]: " JWT_REFRESH_EXPIRY
    JWT_REFRESH_EXPIRY=${JWT_REFRESH_EXPIRY:-"7d"}
    validate_input "$JWT_REFRESH_EXPIRY" "JWT Refresh Expiry"
fi
if [ -z "${MT_API:-}" ]; then
    read -p "Enter MT API Key [Default: none]: " MT_API
    MT_API=${MT_API:-""}
    validate_input "$MT_API" "MT API Key"
fi
if [ -z "${REDIS_HOST:-}" ]; then
    read -p "Enter Redis Host [Default: 127.0.0.1]: " REDIS_HOST
    REDIS_HOST=${REDIS_HOST:-"127.0.0.1"}
    validate_input "$REDIS_HOST" "Redis Host"
fi
if [ -z "${REDIS_PORT:-}" ]; then
    read -p "Enter Redis Port [Default: 6379]: " REDIS_PORT
    REDIS_PORT=${REDIS_PORT:-"6379"}
    validate_numeric_input "$REDIS_PORT" "Redis Port"
fi
if [ -z "${REDIS_DB:-}" ]; then
    read -p "Enter Redis DB [Default: 0]: " REDIS_DB
    REDIS_DB=${REDIS_DB:-"0"}
    validate_numeric_input "$REDIS_DB" "Redis DB"
fi
if [ -z "${REDIS_STORAGE_URI:-}" ]; then
    read -p "Enter Redis Storage URI [Default: redis://127.0.0.1:6379/0]: " REDIS_STORAGE_URI
    REDIS_STORAGE_URI=${REDIS_STORAGE_URI:-"redis://127.0.0.1:6379/0"}
    validate_input "$REDIS_STORAGE_URI" "Redis Storage URI"
fi
if [ -z "${MAIL_DEFAULT_SENDER:-}" ]; then
    read -p "Enter Mail Default Sender (e.g., noreply@rohanbatra.in) [Default: noreply@rohanbatra.in]: " MAIL_DEFAULT_SENDER
    MAIL_DEFAULT_SENDER=${MAIL_DEFAULT_SENDER:-"noreply@rohanbatra.in"}
    validate_input "$MAIL_DEFAULT_SENDER" "Mail Default Sender"
fi
if [ -z "${MAIL_SENDER_NAME:-}" ]; then
    read -p "Enter Mail Sender Name [Default: Rohan Batra]: " MAIL_SENDER_NAME
    MAIL_SENDER_NAME=${MAIL_SENDER_NAME:-"Rohan Batra"}
    validate_input "$MAIL_SENDER_NAME" "Mail Sender Name"
fi

# Set default values
MONGO_URL=${MONGO_URL:-"mongodb://127.0.0.1:27017"}
REDIS_HOST=${REDIS_HOST:-"127.0.0.1"}
REDIS_PORT=${REDIS_PORT:-"6379"}
REDIS_DB=${REDIS_DB:-"0"}
REDIS_STORAGE_URI=${REDIS_STORAGE_URI:-"redis://127.0.0.1:6379/0"}

# Export configuration values as environment variables
log "Exporting configuration values as environment variables..."
export MONGO_URL="$MONGO_URL"
export MONGO_DB_NAME="$MONGO_DB_NAME"
export SECRET_KEY="$SECRET_KEY"
export JWT_EXPIRY="$JWT_EXPIRY"
export JWT_REFRESH_EXPIRY="$JWT_REFRESH_EXPIRY"
export MT_API="$MT_API"
export REDIS_HOST="$REDIS_HOST"
export REDIS_PORT="$REDIS_PORT"
export REDIS_DB="$REDIS_DB"
export REDIS_STORAGE_URI="$REDIS_STORAGE_URI"
export MAIL_DEFAULT_SENDER="$MAIL_DEFAULT_SENDER"
export MAIL_SENDER_NAME="$MAIL_SENDER_NAME"

# Backup existing .sbd_config.json if it exists
if [ -f .sbd_config.json ]; then
    log "Backing up existing .sbd_config.json..."
    cp .sbd_config.json .sbd_config.json.bak
    if [ $? -ne 0 ]; then
        echo "Error: Failed to backup existing .sbd_config.json. Exiting." >&2
        exit 1
    fi
    log "Backup created: .sbd_config.json.bak"
fi

# Generate .sbd_config.json
log "Generating .sbd_config.json..."
cat <<EOL > .sbd_config.json
{
  "MONGO_URL": "$MONGO_URL",
  "MONGO_DB_NAME": "$MONGO_DB_NAME",
  "SECRET_KEY": "$SECRET_KEY",
  "JWT_EXPIRY": "$JWT_EXPIRY",
  "JWT_REFRESH_EXPIRY": "$JWT_REFRESH_EXPIRY",
  "MT_API": "$MT_API",
  "REDIS_HOST": "$REDIS_HOST",
  "REDIS_PORT": "$REDIS_PORT",
  "REDIS_DB": "$REDIS_DB",
  "REDIS_STORAGE_URI": "$REDIS_STORAGE_URI",
  "MAIL_DEFAULT_SENDER": "$MAIL_DEFAULT_SENDER",
  "MAIL_SENDER_NAME": "$MAIL_SENDER_NAME"
}
EOL

if [ $? -ne 0 ]; then
    echo "Error: Failed to write .sbd_config.json. Exiting." >&2
    exit 1
fi

log ".sbd_config.json has been generated successfully."

# Determine the profile file to update
if [ -n "${ZSH_VERSION:-}" ]; then
    PROFILE_FILE="$HOME/.zshrc"
else
    PROFILE_FILE="$HOME/.bashrc"
fi

log "Making environment variables persistent in $PROFILE_FILE..."
cat <<EOL >> $PROFILE_FILE
# Exported by generate_config.sh
export MONGO_URL="$MONGO_URL"
export MONGO_DB_NAME="$MONGO_DB_NAME"
export SECRET_KEY="$SECRET_KEY"
export JWT_EXPIRY="$JWT_EXPIRY"
export JWT_REFRESH_EXPIRY="$JWT_REFRESH_EXPIRY"
export MT_API="$MT_API"
export REDIS_HOST="$REDIS_HOST"
export REDIS_PORT="$REDIS_PORT"
export REDIS_DB="$REDIS_DB"
export REDIS_STORAGE_URI="$REDIS_STORAGE_URI"
export MAIL_DEFAULT_SENDER="$MAIL_DEFAULT_SENDER"
export MAIL_SENDER_NAME="$MAIL_SENDER_NAME"
EOL

if [ $? -ne 0 ]; then
    echo "Error: Failed to update $PROFILE_FILE. Exiting." >&2
    exit 1
fi

# Source the updated profile file to apply changes immediately
if [ -n "$PS1" ]; then
    log "Sourcing $PROFILE_FILE to apply changes..."
    source $PROFILE_FILE
    if [ $? -ne 0 ]; then
        echo "Error: Failed to source $PROFILE_FILE. Please source it manually by running 'source $PROFILE_FILE'." >&2
        exit 1
    fi
    log "Environment variables have been applied successfully."
else
    log "Non-interactive shell detected. Please source $PROFILE_FILE manually to apply changes."
fi