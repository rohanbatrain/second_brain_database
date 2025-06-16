#!/bin/bash

# Test account creation and authentication script
# This script tests the auth endpoints by creating a test user and logging in

set -e  # Exit on any error

# Configuration
BASE_URL="http://localhost:8000"

# Generate random user details for each test run
RANDOM_ID=$(date +%s)$(shuf -i 1000-9999 -n 1)
TEST_USERNAME="testuser_${RANDOM_ID}"
TEST_EMAIL="test_${RANDOM_ID}@example.com"
TEST_PASSWORD="TestPass123!"

echo "🧪 Testing Second Brain Database Authentication"
echo "=============================================="

# Function to make HTTP requests with error handling
make_request() {
    local method=$1
    local endpoint=$2
    local data=$3
    local headers=$4
    
    echo "📡 Making $method request to $endpoint"
    
    if [ -n "$data" ]; then
        if [ -n "$headers" ]; then
            curl -s -X "$method" \
                -H "Content-Type: application/json" \
                -H "$headers" \
                -d "$data" \
                "$BASE_URL$endpoint"
        else
            curl -s -X "$method" \
                -H "Content-Type: application/json" \
                -d "$data" \
                "$BASE_URL$endpoint"
        fi
    else
        if [ -n "$headers" ]; then
            curl -s -X "$method" \
                -H "$headers" \
                "$BASE_URL$endpoint"
        else
            curl -s -X "$method" \
                "$BASE_URL$endpoint"
        fi
    fi
}

# Check if server is running
echo "🔍 Checking if server is running..."
if ! curl -s "$BASE_URL/health" > /dev/null 2>&1; then
    echo "❌ Server is not running at $BASE_URL"
    echo "Please start the server first with: uvicorn main:app --reload"
    exit 1
fi
echo "✅ Server is running"

echo ""
echo "1️⃣  Testing User Registration"
echo "-----------------------------"

# Register test user
REGISTER_DATA=$(cat <<EOF
{
    "username": "$TEST_USERNAME",
    "email": "$TEST_EMAIL",
    "password": "$TEST_PASSWORD"
}
EOF
)

REGISTER_RESPONSE=$(make_request "POST" "/auth/register" "$REGISTER_DATA")
REGISTER_STATUS=$?

if [ $REGISTER_STATUS -eq 0 ]; then
    echo "✅ User registration successful"
    echo "Response: $REGISTER_RESPONSE" | jq '.' 2>/dev/null || echo "Response: $REGISTER_RESPONSE"
else
    echo "❌ User registration failed"
    echo "Response: $REGISTER_RESPONSE"
fi

echo ""
echo "2️⃣  Testing User Login"
echo "----------------------"

# Login with test user (OAuth2 form data)
LOGIN_RESPONSE=$(curl -s -X POST \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$TEST_EMAIL&password=$TEST_PASSWORD" \
    "$BASE_URL/auth/login")

LOGIN_STATUS=$?

if [ $LOGIN_STATUS -eq 0 ] && echo "$LOGIN_RESPONSE" | grep -q "access_token"; then
    echo "✅ User login successful"
    echo "Response: $LOGIN_RESPONSE" | jq '.' 2>/dev/null || echo "Response: $LOGIN_RESPONSE"
    
    # Extract access token
    ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token' 2>/dev/null || echo "")
    
    if [ -n "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "null" ]; then
        echo ""
        echo "3️⃣  Testing Protected Endpoint (/auth/me)"
        echo "----------------------------------------"
        
        # Test protected endpoint
        ME_RESPONSE=$(make_request "GET" "/auth/me" "" "Authorization: Bearer $ACCESS_TOKEN")
        
        if echo "$ME_RESPONSE" | grep -q "$TEST_USERNAME"; then
            echo "✅ Protected endpoint access successful"
            echo "Response: $ME_RESPONSE" | jq '.' 2>/dev/null || echo "Response: $ME_RESPONSE"
        else
            echo "❌ Protected endpoint access failed"
            echo "Response: $ME_RESPONSE"
        fi
        
        echo ""
        echo "4️⃣  Testing Token Refresh"
        echo "-------------------------"
        
        # Test token refresh
        REFRESH_RESPONSE=$(make_request "POST" "/auth/refresh" "" "Authorization: Bearer $ACCESS_TOKEN")
        
        if echo "$REFRESH_RESPONSE" | grep -q "access_token"; then
            echo "✅ Token refresh successful"
            echo "Response: $REFRESH_RESPONSE" | jq '.' 2>/dev/null || echo "Response: $REFRESH_RESPONSE"
        else
            echo "❌ Token refresh failed"
            echo "Response: $REFRESH_RESPONSE"
        fi
        
        echo ""
        echo "5️⃣  Testing Password Change"
        echo "---------------------------"
        
        NEW_PASSWORD="NewTestPass456!"
        CHANGE_PASSWORD_DATA=$(cat <<EOF
{
    "old_password": "$TEST_PASSWORD",
    "new_password": "$NEW_PASSWORD"
}
EOF
)
        
        CHANGE_PASSWORD_RESPONSE=$(make_request "PUT" "/auth/change-password" "$CHANGE_PASSWORD_DATA" "Authorization: Bearer $ACCESS_TOKEN")
        
        if echo "$CHANGE_PASSWORD_RESPONSE" | grep -q "Password changed successfully"; then
            echo "✅ Password change successful"
            echo "Response: $CHANGE_PASSWORD_RESPONSE" | jq '.' 2>/dev/null || echo "Response: $CHANGE_PASSWORD_RESPONSE"
            
            # Test login with new password
            echo ""
            echo "6️⃣  Testing Login with New Password"
            echo "-----------------------------------"
            
            NEW_LOGIN_RESPONSE=$(curl -s -X POST \
                -H "Content-Type: application/x-www-form-urlencoded" \
                -d "username=$TEST_EMAIL&password=$NEW_PASSWORD" \
                "$BASE_URL/auth/login")
            
            if echo "$NEW_LOGIN_RESPONSE" | grep -q "access_token"; then
                echo "✅ Login with new password successful"
                echo "Response: $NEW_LOGIN_RESPONSE" | jq '.' 2>/dev/null || echo "Response: $NEW_LOGIN_RESPONSE"
            else
                echo "❌ Login with new password failed"
                echo "Response: $NEW_LOGIN_RESPONSE"
            fi
        else
            echo "❌ Password change failed"
            echo "Response: $CHANGE_PASSWORD_RESPONSE"
        fi
        
        echo ""
        echo "7️⃣  Testing Logout"
        echo "------------------"
        
        # Test logout
        LOGOUT_RESPONSE=$(make_request "POST" "/auth/logout" "" "Authorization: Bearer $ACCESS_TOKEN")
        
        if echo "$LOGOUT_RESPONSE" | grep -q "Successfully logged out"; then
            echo "✅ Logout successful"
            echo "Response: $LOGOUT_RESPONSE" | jq '.' 2>/dev/null || echo "Response: $LOGOUT_RESPONSE"
        else
            echo "❌ Logout failed"
            echo "Response: $LOGOUT_RESPONSE"
        fi
    else
        echo "❌ Could not extract access token from login response"
    fi
else
    echo "❌ User login failed"
    echo "Response: $LOGIN_RESPONSE"
fi

echo ""
echo "8️⃣  Testing Invalid Login"
echo "-------------------------"

# Test invalid login
INVALID_LOGIN_RESPONSE=$(curl -s -X POST \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$TEST_EMAIL&password=wrongpassword" \
    "$BASE_URL/auth/login")

if echo "$INVALID_LOGIN_RESPONSE" | grep -q "Invalid credentials"; then
    echo "✅ Invalid login correctly rejected"
    echo "Response: $INVALID_LOGIN_RESPONSE" | jq '.' 2>/dev/null || echo "Response: $INVALID_LOGIN_RESPONSE"
else
    echo "❌ Invalid login test failed"
    echo "Response: $INVALID_LOGIN_RESPONSE"
fi

echo ""
echo "🧹 Cleanup: Removing Test User"
echo "==============================="
echo "Test user details for this run:"
echo "Username: $TEST_USERNAME"
echo "Email: $TEST_EMAIL"
echo "Note: Manual cleanup required - delete user '$TEST_USERNAME' from database if needed"

echo ""
echo "🎉 Authentication testing completed!"
echo "Check the results above for any failures."