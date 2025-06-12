#!/bin/bash

# Prompt user for environment choice
echo "Choose the environment to run the application:"
echo "1. Docker"
echo "2. Bare Metal"
read -p "Enter your choice (1 or 2): " choice

# Prompt user for configuration values
read -p "Enter MongoDB Database Name: " MONGO_DB_NAME
read -p "Enter Secret Key (at least 32 characters): " SECRET_KEY
read -p "Enter JWT Expiry (e.g., 1h): " JWT_EXPIRY
read -p "Enter JWT Refresh Expiry (e.g., 7d): " JWT_REFRESH_EXPIRY
read -p "Enter Mail Default Sender (e.g., noreply@example.com): " MAIL_DEFAULT_SENDER
read -p "Enter Mail Sender Name: " MAIL_SENDER_NAME
read -p "Enter MT API Key (if any, leave blank if not applicable): " MT_API

# Set default values
MONGO_URL="mongodb://127.0.0.1:27017"
REDIS_HOST="127.0.0.1"
REDIS_PORT="6379"
REDIS_DB="0"
REDIS_STORAGE_URI="redis://127.0.0.1:6379/0"

# Adjust values based on the environment
if [ "$choice" -eq 1 ]; then
    echo "Configuring for Docker environment..."
    MONGO_URL="mongodb://mongo:27017"
    REDIS_HOST="redis"
    REDIS_STORAGE_URI="redis://redis:6379/0"
elif [ "$choice" -eq 2 ]; then
    echo "Configuring for Bare Metal environment..."
else
    echo "Invalid choice. Exiting."
    exit 1
fi

# Generate .sbd_config.json
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

echo ".sbd_config.json has been generated successfully."