#!/bin/bash
# Quick curl test for plan validation security in signup endpoint.
# This script tests the plan validation by sending different registration requests.

BASE_URL="http://localhost:8000"
echo "🔐 Testing Plan Validation Security via curl"
echo "============================================="

# Test 1: Valid free plan registration
echo -e "\n1️⃣ Testing valid free plan registration..."
curl -s -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testfree",
    "email": "testfree@example.com", 
    "password": "TestPass123!",
    "plan": "free"
  }' | jq -r '.access_token // .detail // "No response"' | head -c 50
echo "..."

# Test 2: Invalid premium plan attempt
echo -e "\n2️⃣ Testing premium plan bypass attempt..."
response=$(curl -s -w "%{http_code}" -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testpremium", 
    "email": "testpremium@example.com",
    "password": "TestPass123!",
    "plan": "premium"
  }')

http_code="${response: -3}"
response_body="${response%???}"

if [ "$http_code" == "422" ]; then
  echo "✅ Premium plan correctly blocked (422 Validation Error)"
elif [ "$http_code" == "400" ]; then
  echo "✅ Premium plan blocked by business logic (400 Bad Request)"
elif [ "$http_code" == "200" ]; then
  echo "❌ SECURITY VULNERABILITY: Premium plan registration allowed!"
else
  echo "⚠️ Unexpected response code: $http_code"
fi

# Test 3: Invalid enterprise plan attempt
echo -e "\n3️⃣ Testing enterprise plan bypass attempt..."
response=$(curl -s -w "%{http_code}" -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testenterprise",
    "email": "testenterprise@example.com", 
    "password": "TestPass123!",
    "plan": "enterprise"
  }')

http_code="${response: -3}"
if [ "$http_code" == "422" ]; then
  echo "✅ Enterprise plan correctly blocked (422 Validation Error)" 
elif [ "$http_code" == "400" ]; then
  echo "✅ Enterprise plan blocked by business logic (400 Bad Request)"
elif [ "$http_code" == "200" ]; then
  echo "❌ SECURITY VULNERABILITY: Enterprise plan registration allowed!"
else
  echo "⚠️ Unexpected response code: $http_code"
fi

# Test 4: Random plan name attempt  
echo -e "\n4️⃣ Testing random plan name..."
response=$(curl -s -w "%{http_code}" -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testrandom",
    "email": "testrandom@example.com",
    "password": "TestPass123!", 
    "plan": "super_premium_ultra"
  }')

http_code="${response: -3}"
if [ "$http_code" == "422" ]; then
  echo "✅ Random plan correctly blocked (422 Validation Error)"
elif [ "$http_code" == "400" ]; then
  echo "✅ Random plan blocked by business logic (400 Bad Request)" 
elif [ "$http_code" == "200" ]; then
  echo "❌ SECURITY VULNERABILITY: Random plan registration allowed!"
else
  echo "⚠️ Unexpected response code: $http_code"
fi

echo -e "\n============================================="
echo "🔒 Plan validation security test complete!"
echo "✅ Only 'free' plans should be accepted for new registrations"