#!/bin/bash

# Simple Family API Test
set -e

BASE_URL="http://localhost:8000"
TEST_USER="test_user_$(date +%s)"
TEST_EMAIL="${TEST_USER}@example.com"
TEST_PASSWORD="TestPass123!"

echo "=== Testing Family Management API ==="

# Test 1: Health Check
echo "1. Health Check..."
curl -s "$BASE_URL/health" | grep -q "healthy" && echo "✓ Health check passed" || echo "✗ Health check failed"

# Test 2: User Registration
echo "2. User Registration..."
REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$TEST_USER\",\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}")

echo "Register response: $REGISTER_RESPONSE"

# Test 3: User Login
echo "3. User Login..."
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$TEST_USER\",\"password\":\"$TEST_PASSWORD\"}")

echo "Login response: $LOGIN_RESPONSE"

# Extract token (simple grep approach)
ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -n "$ACCESS_TOKEN" ]; then
    echo "✓ Login successful, token extracted"
    
    # Test 4: Create Family
    echo "4. Creating Family..."
    FAMILY_RESPONSE=$(curl -s -X POST "$BASE_URL/family/create" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -d "{\"name\":\"Test Family\"}")
    
    echo "Family creation response: $FAMILY_RESPONSE"
    
    # Test 5: Get User Families
    echo "5. Getting User Families..."
    FAMILIES_RESPONSE=$(curl -s -X GET "$BASE_URL/family/my-families" \
      -H "Authorization: Bearer $ACCESS_TOKEN")
    
    echo "User families response: $FAMILIES_RESPONSE"
    
    # Test 6: Check Family Limits
    echo "6. Checking Family Limits..."
    LIMITS_RESPONSE=$(curl -s -X GET "$BASE_URL/family/limits" \
      -H "Authorization: Bearer $ACCESS_TOKEN")
    
    echo "Family limits response: $LIMITS_RESPONSE"
    
    echo "✓ Basic family functionality tests completed"
else
    echo "✗ Failed to extract access token"
fi

echo "=== Test Complete ==="