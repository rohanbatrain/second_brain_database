#!/bin/bash
BASE_URL="http://localhost:5000/auth"

login_user() {
    curl -X POST "$BASE_URL/login" \
        -H "Content-Type: application/json" \
        -d '{
            "email": "testuser@example.com",
            "password": "password123"
        }'
}

# Login the user
echo "Logging in user..."
login_user