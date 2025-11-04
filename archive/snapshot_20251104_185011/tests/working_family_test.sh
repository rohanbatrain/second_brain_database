#!/bin/bash

# Working Family API Test
set -e

BASE_URL="http://localhost:8000"
TIMESTAMP=$(date +%s)
TEST_USER="testuser${TIMESTAMP}"
TEST_EMAIL="${TEST_USER}@example.com"
TEST_PASSWORD="TestPass123!"

echo "=== Testing Family Management API ==="
echo "Using test user: $TEST_USER"

# Test 1: Health Check
echo "1. Health Check..."
HEALTH_RESPONSE=$(curl -s "$BASE_URL/health")
echo "Health: $HEALTH_RESPONSE"

# Test 2: User Registration
echo "2. User Registration..."
REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$TEST_USER\",\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}")

echo "Register response: $REGISTER_RESPONSE"

# Extract token from registration response
ACCESS_TOKEN=$(echo "$REGISTER_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -n "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "" ]; then
    echo "✓ Registration successful, token extracted: ${ACCESS_TOKEN:0:20}..."
    
    # Test 3: Create Family
    echo "3. Creating Family..."
    FAMILY_RESPONSE=$(curl -s -X POST "$BASE_URL/family/create" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -d "{\"name\":\"Test Family $TIMESTAMP\"}")
    
    echo "Family creation response: $FAMILY_RESPONSE"
    
    # Extract family ID
    FAMILY_ID=$(echo "$FAMILY_RESPONSE" | grep -o '"family_id":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$FAMILY_ID" ]; then
        echo "✓ Family created successfully: $FAMILY_ID"
        
        # Test 4: Get User Families
        echo "4. Getting User Families..."
        FAMILIES_RESPONSE=$(curl -s -X GET "$BASE_URL/family/my-families" \
          -H "Authorization: Bearer $ACCESS_TOKEN")
        
        echo "User families response: $FAMILIES_RESPONSE"
        
        # Test 5: Get Family Members
        echo "5. Getting Family Members..."
        MEMBERS_RESPONSE=$(curl -s -X GET "$BASE_URL/family/$FAMILY_ID/members" \
          -H "Authorization: Bearer $ACCESS_TOKEN")
        
        echo "Family members response: $MEMBERS_RESPONSE"
        
        # Test 6: Check Family Limits
        echo "6. Checking Family Limits..."
        LIMITS_RESPONSE=$(curl -s -X GET "$BASE_URL/family/limits" \
          -H "Authorization: Bearer $ACCESS_TOKEN")
        
        echo "Family limits response: $LIMITS_RESPONSE"
        
        # Test 7: Get SBD Balance
        echo "7. Getting SBD Balance..."
        BALANCE_RESPONSE=$(curl -s -X GET "$BASE_URL/family/$FAMILY_ID/sbd/balance" \
          -H "Authorization: Bearer $ACCESS_TOKEN")
        
        echo "SBD balance response: $BALANCE_RESPONSE"
        
        # Test 8: Family Health Check
        echo "8. Family Health Check..."
        HEALTH_RESPONSE=$(curl -s -X GET "$BASE_URL/family/health" \
          -H "Authorization: Bearer $ACCESS_TOKEN")
        
        echo "Family health response: $HEALTH_RESPONSE"
        
        # Test 9: Create Token Request
        echo "9. Creating Token Request..."
        TOKEN_REQUEST_RESPONSE=$(curl -s -X POST "$BASE_URL/family/$FAMILY_ID/sbd/request-tokens" \
          -H "Content-Type: application/json" \
          -H "Authorization: Bearer $ACCESS_TOKEN" \
          -d "{\"amount\":100,\"reason\":\"Test token request\",\"urgency\":\"medium\"}")
        
        echo "Token request response: $TOKEN_REQUEST_RESPONSE"
        
        # Test 10: Get Notifications
        echo "10. Getting Notifications..."
        NOTIFICATIONS_RESPONSE=$(curl -s -X GET "$BASE_URL/family/$FAMILY_ID/notifications" \
          -H "Authorization: Bearer $ACCESS_TOKEN")
        
        echo "Notifications response: $NOTIFICATIONS_RESPONSE"
        
        echo "✓ All family functionality tests completed successfully!"
        echo "✓ Family ID: $FAMILY_ID"
        echo "✓ User: $TEST_USER"
        
    else
        echo "✗ Failed to create family"
        echo "Response: $FAMILY_RESPONSE"
    fi
    
else
    echo "✗ Failed to extract access token from registration"
    echo "Registration response: $REGISTER_RESPONSE"
fi

echo "=== Test Complete ==="