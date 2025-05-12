#!/bin/bash
BASE_URL="http://localhost:5000/auth"

login_user() {
    curl -X POST "$BASE_URL/resend" \
        -H "Content-Type: application/json" \
        -d '{
            "email": "test@rohanbatra.in"
        }'
}

# Login the user
echo "Logging in user..."
login_user