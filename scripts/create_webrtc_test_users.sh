#!/bin/bash

# WebRTC Test Users Setup Script
# Creates two test users, then you manually verify emails, then get JWT tokens

set -e  # Exit on error

API_URL="http://localhost:8000"
TURNSTILE_TOKEN="dummy-token-for-testing"  # Adjust if needed

echo "🚀 Creating WebRTC Test Users (Manual Email Verification)"
echo "=========================================================="
echo ""

# Function to create user
create_user() {
    local username=$1
    local email=$2
    local password=$3

    echo "📝 Creating user: $username ($email)"

    response=$(curl -s -X POST "$API_URL/auth/register" \
        -H "Content-Type: application/json" \
        -d "{
            \"username\": \"$username\",
            \"email\": \"$email\",
            \"password\": \"$password\",
            \"turnstile_token\": \"$TURNSTILE_TOKEN\"
        }")

    echo "Response: $response"
    echo ""
}

# Function to login and get JWT token
login_user() {
    local username=$1
    local password=$2

    echo "🔑 Logging in: $username"

    response=$(curl -s -X POST "$API_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d "{
            \"username\": \"$username\",
            \"password\": \"$password\"
        }")

    # Extract token using python
    token=$(echo "$response" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('access_token', 'ERROR'))" 2>/dev/null || echo "ERROR")

    if [ "$token" = "ERROR" ] || [ -z "$token" ]; then
        echo "   ❌ Failed to get token"
        echo "   Response: $response"
        echo ""
        return 1
    fi

    echo "   ✅ Token received:"
    echo "   $token"
    echo ""

    # Store in variable for later use
    if [ "$username" = "webrtc_user1" ]; then
        USER1_TOKEN="$token"
    else
        USER2_TOKEN="$token"
    fi
}

# Create User 1
echo "👤 USER 1"
echo "--------"
create_user "webrtc_user1" "webrtc1@test.com" "TestPass123!"

echo "👤 USER 2"
echo "--------"
create_user "webrtc_user2" "webrtc2@test.com" "TestPass456!"

echo ""
echo "� MANUAL EMAIL VERIFICATION REQUIRED"
echo "======================================"
echo ""
echo "⚠️  Please check your email and click the verification links for:"
echo "   - webrtc1@test.com"
echo "   - webrtc2@test.com"
echo ""
echo "💡 If using a local email server, check the logs or database directly."
echo ""
echo "🔍 To verify manually via API (if you have the verification tokens):"
echo "   curl -X POST $API_URL/auth/verify-email \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"token\": \"YOUR_VERIFICATION_TOKEN\"}'"
echo ""
echo "⏳ Press Enter when you've verified both emails..."
read -p ""

echo ""
echo "🔑 Getting JWT Tokens"
echo "======================"

echo "👤 USER 1 LOGIN"
echo "---------------"
login_user "webrtc_user1" "TestPass123!"

echo "👤 USER 2 LOGIN"
echo "---------------"
login_user "webrtc_user2" "TestPass456!"

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "📋 Copy these tokens into webrtc_test.html:"
echo ""
echo "USER 1 TOKEN (webrtc_user1):"
echo "$USER1_TOKEN"
echo ""
echo "USER 2 TOKEN (webrtc_user2):"
echo "$USER2_TOKEN"
echo ""
echo "🌐 Now open webrtc_test.html in TWO separate browser windows/tabs"
echo "   - Window 1: Paste User 1 token"
echo "   - Window 2: Paste User 2 token"
echo "   - Click 'Connect to Room' in both windows"
echo "   - Click 'Start Call' to begin video chat"
echo ""
