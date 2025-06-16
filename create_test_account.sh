#!/bin/bash

# API base URL
API_URL="http://localhost:8000/auth"

# Test account credentials
USERNAME="testuser"
PASSWORD="testpassword"

# Register the test account
register_response=$(curl -s -X POST "$API_URL/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "'$USERNAME'", "password": "'$PASSWORD'"}')

echo "Register Response: $register_response"

# Login with the test account
login_response=$(curl -s -X POST "$API_URL/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$USERNAME&password=$PASSWORD")

echo "Login Response: $login_response"