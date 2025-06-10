#!/bin/bash

# Base URL of the API
BASE_URL="http://auth"

# Register a new user
register_user() {
    curl -X POST "$BASE_URL/register" \
        -H "Content-Type: application/json" \
        -d '{
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "password123",
            "plan": "free",
            "team": []
        }'
}




# Register the user
echo "Registering user..."
register_user

